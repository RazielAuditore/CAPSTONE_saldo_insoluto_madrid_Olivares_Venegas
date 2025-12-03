"""
Rutas de gestión de documentos
"""
from flask import request, jsonify, send_file
import io
import zipfile
from psycopg2.extras import RealDictCursor
from utils.database import get_db_connection
from utils.helpers import allowed_file, get_file_hash, get_mime_type
from werkzeug.utils import secure_filename
from middleware.auth import login_required
from utils.helpers import ALLOWED_EXTENSIONS, MAX_FILE_SIZE

def register_routes(app):
    """Registrar rutas de documentos"""
    
    @app.route('/api/upload-documento', methods=['POST'])
    @login_required
    def upload_documento():
        """Subir un documento como BLOB"""
        print('📁 Iniciando subida de archivo...')
        print(f'📋 Form data recibido: {dict(request.form)}')
        print(f'📋 Files recibidos: {list(request.files.keys())}')
        
        conn = get_db_connection()
        if not conn:
            return jsonify({'error': 'Error de conexión a la base de datos'}), 500
        
        try:
            # Verificar que se envió un archivo
            if 'archivo' not in request.files:
                print('❌ No se encontró archivo en la petición')
                return jsonify({'error': 'No se encontró archivo en la petición'}), 400
            
            file = request.files['archivo']
            print(f'📄 Archivo recibido: {file.filename}')
            
            if file.filename == '':
                print('❌ No se seleccionó ningún archivo')
                return jsonify({'error': 'No se seleccionó ningún archivo'}), 400
            
            # Verificar extensión permitida
            if not allowed_file(file.filename):
                print(f'❌ Extensión no permitida: {file.filename}')
                return jsonify({
                    'error': f'Extensión no permitida. Extensiones válidas: {", ".join(ALLOWED_EXTENSIONS)}'
                }), 400
            
            # Leer el archivo
            file_data = file.read()
            
            # Verificar tamaño
            if len(file_data) > MAX_FILE_SIZE:
                return jsonify({
                    'error': f'Archivo demasiado grande. Tamaño máximo: {MAX_FILE_SIZE // (1024*1024)}MB'
                }), 400
            
            # Obtener datos adicionales
            solicitud_id = request.form.get('solicitud_id')
            doc_tipo_id = request.form.get('doc_tipo_id', 1)
            observaciones = request.form.get('observaciones', '')
            
            print(f'🆔 Solicitud ID recibido: "{solicitud_id}" (tipo: {type(solicitud_id)})')
            
            if not solicitud_id or solicitud_id == 'undefined':
                print('❌ ID de solicitud requerido')
                return jsonify({'error': 'ID de solicitud requerido'}), 400
            
            # Validar que solicitud_id sea un número
            try:
                solicitud_id = int(solicitud_id)
                print(f'✅ Solicitud ID convertido a entero: {solicitud_id}')
            except (ValueError, TypeError):
                print(f'❌ Error convirtiendo solicitud_id a entero: {solicitud_id}')
                return jsonify({'error': 'ID de solicitud debe ser un número válido'}), 400
            
            # Generar hash del archivo
            file_hash = get_file_hash(file_data)
            
            # Obtener tipo MIME
            mime_type = get_mime_type(file.filename)
            
            # Nombre seguro del archivo
            safe_filename = secure_filename(file.filename)
            
            cur = conn.cursor()
            
            # Obtener expediente_id y estado de la solicitud
            cur.execute("""
                SELECT expediente_id, estado FROM app.solicitudes WHERE id = %s
            """, (solicitud_id,))
            
            solicitud_result = cur.fetchone()
            if not solicitud_result:
                return jsonify({'error': 'Solicitud no encontrada'}), 404
            
            expediente_id = solicitud_result[0]
            estado_solicitud = solicitud_result[1]
            
            # Bloquear subida de documentos si está en pendiente (revisión de jefatura)
            if estado_solicitud == 'pendiente':
                return jsonify({'error': 'No se pueden agregar documentos a un expediente que está en revisión de jefatura. Debe estar rechazado para poder agregar documentos.'}), 400
            
            # Insertar el documento
            cur.execute("""
                INSERT INTO app.documentos_saldo_insoluto 
                (expediente_id, solicitud_id, doc_tipo_id, doc_nombre_archivo, doc_archivo_blob, 
                 doc_mime_type, doc_tamano_bytes, doc_sha256, doc_ruta_storage, doc_observaciones, 
                 doc_estado, doc_fecha_subida)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'subido', NOW())
                RETURNING id
            """, (
                expediente_id, solicitud_id, doc_tipo_id, safe_filename, file_data,
                mime_type, len(file_data), file_hash, "/api/download-documento/temp", observaciones
            ))
            
            documento_id = cur.fetchone()[0]
            
            # Actualizar la ruta con el ID real del documento
            cur.execute("""
                UPDATE app.documentos_saldo_insoluto 
                SET doc_ruta_storage = %s
                WHERE id = %s
            """, (f"/api/download-documento/{documento_id}", documento_id))
            
            conn.commit()
            cur.close()
            conn.close()
            
            print(f'📁 Archivo subido: {safe_filename} ({len(file_data)} bytes)')
            print(f'🔗 Ruta generada: /api/download-documento/{documento_id}')
            
            return jsonify({
                'success': True,
                'message': 'Archivo subido exitosamente',
                'data': {
                    'documento_id': documento_id,
                    'expediente_id': expediente_id,
                    'nombre_archivo': safe_filename,
                    'tamano_bytes': len(file_data),
                    'mime_type': mime_type,
                    'sha256_hash': file_hash,
                    'ruta_storage': f"/api/download-documento/{documento_id}"
                }
            }), 201
            
        except Exception as e:
            print(f'❌ Error subiendo archivo: {e}')
            if 'conn' in locals():
                conn.rollback()
                conn.close()
            return jsonify({'error': f'Error interno del servidor: {str(e)}'}), 500

    @app.route('/api/download-documento/<int:documento_id>', methods=['GET'])
    def download_documento(documento_id):
        """Descargar un documento por ID"""
        conn = get_db_connection()
        if not conn:
            return jsonify({'error': 'Error de conexión a la base de datos'}), 500
        
        try:
            cur = conn.cursor()
            
            # Obtener el documento
            cur.execute("""
                SELECT doc_nombre_archivo, doc_archivo_blob, doc_mime_type, doc_tamano_bytes
                FROM app.documentos_saldo_insoluto 
                WHERE id = %s
            """, (documento_id,))
            
            documento = cur.fetchone()
            if not documento:
                return jsonify({'error': 'Documento no encontrado'}), 404
            
            nombre_archivo, archivo_blob, mime_type, tamano_bytes = documento
            
            cur.close()
            conn.close()
            
            # Crear objeto BytesIO para enviar el archivo
            file_obj = io.BytesIO(archivo_blob)
            
            print(f'📥 Descargando archivo: {nombre_archivo} ({tamano_bytes} bytes)')
            
            return send_file(
                file_obj,
                mimetype=mime_type,
                as_attachment=True,
                download_name=nombre_archivo
            )
            
        except Exception as e:
            print(f'❌ Error descargando archivo: {e}')
            if 'conn' in locals():
                conn.close()
            return jsonify({'error': f'Error interno del servidor: {str(e)}'}), 500

    @app.route('/api/documentos/<int:solicitud_id>', methods=['GET'])
    def listar_documentos(solicitud_id):
        """Listar todos los documentos de una solicitud"""
        conn = get_db_connection()
        if not conn:
            return jsonify({'error': 'Error de conexión a la base de datos'}), 500
        
        try:
            cur = conn.cursor(cursor_factory=RealDictCursor)
            
            # Obtener documentos de la solicitud
            cur.execute("""
                SELECT id, doc_nombre_archivo, doc_mime_type, doc_tamano_bytes, 
                       doc_sha256_hash, doc_estado, doc_observaciones, doc_fecha_subida
                FROM app.documentos_saldo_insoluto 
                WHERE solicitud_id = %s
                ORDER BY doc_fecha_subida DESC
            """, (solicitud_id,))
            
            documentos = cur.fetchall()
            
            cur.close()
            conn.close()
            
            return jsonify({
                'success': True,
                'data': [dict(doc) for doc in documentos]
            }), 200
            
        except Exception as e:
            print(f'❌ Error listando documentos: {e}')
            if 'conn' in locals():
                conn.close()
            return jsonify({'error': f'Error interno del servidor: {str(e)}'}), 500

    @app.route('/api/download-expediente-completo/<int:expediente_id>', methods=['GET'])
    @login_required
    def download_expediente_completo(expediente_id):
        """Descargar todos los documentos del expediente como ZIP"""
        conn = get_db_connection()
        if not conn:
            return jsonify({'error': 'Error de conexión a la base de datos'}), 500
        
        try:
            cur = conn.cursor(cursor_factory=RealDictCursor)
            
            # Obtener todos los documentos del expediente
            cur.execute("""
                SELECT id, doc_nombre_archivo, doc_archivo_blob, doc_mime_type
                FROM app.documentos_saldo_insoluto 
                WHERE expediente_id = %s
                ORDER BY doc_fecha_subida ASC
            """, (expediente_id,))
            
            documentos = cur.fetchall()
            
            if not documentos:
                return jsonify({'error': 'No hay documentos en este expediente'}), 404
            
            # Crear ZIP en memoria
            zip_buffer = io.BytesIO()
            
            with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
                for i, documento in enumerate(documentos):
                    # Usar el nombre del archivo original
                    zip_file.writestr(documento['doc_nombre_archivo'], documento['doc_archivo_blob'])
            
            zip_buffer.seek(0)
            
            cur.close()
            conn.close()
            
            print(f'📦 Generando ZIP con {len(documentos)} documentos para expediente {expediente_id}')
            
            return send_file(
                zip_buffer,
                mimetype='application/zip',
                as_attachment=True,
                download_name=f'expediente_{expediente_id}_completo.zip'
            )
            
        except Exception as e:
            print(f'❌ Error generando ZIP: {e}')
            if 'conn' in locals():
                conn.close()
            return jsonify({'error': f'Error interno del servidor: {str(e)}'}), 500

    @app.route('/api/documentos/<int:documento_id>', methods=['DELETE'])
    @login_required
    def eliminar_documento(documento_id):
        """Eliminar un documento"""
        conn = get_db_connection()
        if not conn:
            return jsonify({'error': 'Error de conexión a la base de datos'}), 500
        
        try:
            cur = conn.cursor()
            
            # Verificar que el documento existe y pertenece a un expediente rechazado/enRevision
            cur.execute("""
                SELECT d.id, d.expediente_id, s.estado
                FROM app.documentos_saldo_insoluto d
                JOIN app.solicitudes s ON d.expediente_id = s.expediente_id
                WHERE d.id = %s
                ORDER BY s.id DESC LIMIT 1
            """, (documento_id,))
            
            documento = cur.fetchone()
            if not documento:
                cur.close()
                conn.close()
                return jsonify({'error': 'Documento no encontrado'}), 404
            
            estado = documento[2]
            if estado != 'rechazado/enRevision':
                cur.close()
                conn.close()
                return jsonify({'error': 'Solo se pueden eliminar documentos de expedientes rechazados en revisión'}), 400
            
            # Eliminar documento
            cur.execute("DELETE FROM app.documentos_saldo_insoluto WHERE id = %s", (documento_id,))
            
            conn.commit()
            cur.close()
            conn.close()
            
            return jsonify({
                'success': True,
                'message': 'Documento eliminado exitosamente'
            }), 200
            
        except Exception as e:
            print(f'❌ Error eliminando documento: {e}')
            if 'conn' in locals():
                conn.rollback()
                conn.close()
            return jsonify({'error': f'Error interno del servidor: {str(e)}'}), 500

