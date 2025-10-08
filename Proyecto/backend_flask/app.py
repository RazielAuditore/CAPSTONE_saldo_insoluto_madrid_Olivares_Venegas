from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
import psycopg2
from psycopg2.extras import RealDictCursor
import os
from datetime import datetime
import json
import hashlib
import hmac
import secrets
import io
import bcrypt
from werkzeug.utils import secure_filename
from config import Config

app = Flask(__name__)
CORS(app)

# Configuración de la aplicación
app.config.from_object(Config)

# Configuración de la base de datos
DB_CONFIG = Config().DATABASE_CONFIG

# Configuración para archivos
ALLOWED_EXTENSIONS = {'pdf', 'png', 'jpg', 'jpeg', 'gif', 'doc', 'docx', 'xls', 'xlsx'}
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB máximo

def get_db_connection():
    """Obtener conexión a la base de datos"""
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        return conn
    except Exception as e:
        print(f"❌ Error conectando a PostgreSQL: {e}")
        return None

def test_connection():
    """Probar la conexión a la base de datos"""
    conn = get_db_connection()
    if conn:
        try:
            cur = conn.cursor()
            cur.execute('SELECT NOW()')
            result = cur.fetchone()
            print('✅ Conectado a PostgreSQL')
            print(f'📅 Hora del servidor: {result[0]}')
            cur.close()
            conn.close()
            return True
        except Exception as e:
            print(f'❌ Error en consulta de prueba: {e}')
            return False
    return False

def allowed_file(filename):
    """Verificar si el archivo tiene una extensión permitida"""
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def get_file_hash(file_data):
    """Generar hash SHA256 del archivo"""
    return hashlib.sha256(file_data).hexdigest()

def get_mime_type(filename):
    """Obtener tipo MIME basado en la extensión del archivo"""
    mime_types = {
        'pdf': 'application/pdf',
        'png': 'image/png',
        'jpg': 'image/jpeg',
        'jpeg': 'image/jpeg',
        'gif': 'image/gif',
        'doc': 'application/msword',
        'docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        'xls': 'application/vnd.ms-excel',
        'xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    }
    ext = filename.rsplit('.', 1)[1].lower()
    return mime_types.get(ext, 'application/octet-stream')

def validar_rut_chileno(rut):
    """Validar RUT chileno con algoritmo de dígito verificador"""
    try:
        print(f"🔍 Validando RUT: '{rut}'")
        
        # Limpiar RUT
        rut_limpio = rut.replace('.', '').replace('-', '').upper()
        print(f"🔍 RUT limpio: '{rut_limpio}'")
        
        if len(rut_limpio) < 8 or len(rut_limpio) > 9:
            print(f"❌ RUT muy corto/largo: {len(rut_limpio)} caracteres")
            return False
        
        # Separar número y dígito verificador
        numero = rut_limpio[:-1]
        dv = rut_limpio[-1]
        print(f"🔍 Número: '{numero}', DV: '{dv}'")
        
        # Validar que el número sea solo dígitos
        if not numero.isdigit():
            return False
        
        # Calcular dígito verificador
        suma = 0
        multiplicador = 2
        
        for digito in reversed(numero):
            suma += int(digito) * multiplicador
            multiplicador = multiplicador + 1 if multiplicador < 7 else 2
        
        resto = suma % 11
        dv_calculado = 11 - resto
        
        if dv_calculado == 11:
            dv_calculado = '0'
        elif dv_calculado == 10:
            dv_calculado = 'K'
        else:
            dv_calculado = str(dv_calculado)
        
        print(f"🔍 DV ingresado: '{dv}', DV calculado: '{dv_calculado}'")
        resultado = dv == dv_calculado
        print(f"🔍 Resultado validación: {resultado}")
        
        return resultado
        
    except Exception:
        return False

def hash_password(password):
    """Encriptar contraseña con bcrypt"""
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')

@app.route('/api/solicitudes', methods=['POST'])
def crear_solicitud():
    """Crear una nueva solicitud de saldo insoluto"""
    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Error de conexión a la base de datos'}), 500
    
    try:
        cur = conn.cursor()
        
        # Iniciar transacción
        cur.execute('BEGIN')
        
        # 1. Crear expediente principal
        expediente_numero = f"EXP-{datetime.now().year}-{datetime.now().strftime('%H%M%S')}"
        cur.execute("""
            INSERT INTO app.expediente (expediente_numero, estado, observaciones)
            VALUES (%s, 'en_proceso', 'Expediente de saldo insoluto creado automáticamente')
            RETURNING id
        """, (expediente_numero,))
        expediente_id = cur.fetchone()[0]
        
        # Datos del formulario
        data = request.get_json()
        
        # Debug: Mostrar los datos recibidos
        print('🔍 Datos recibidos del frontend:')
        print(f'  fal_fecha_defuncion: {data.get("fal_fecha_defuncion", "")}')
        print(f'  fal_comuna_defuncion: {data.get("fal_comuna_defuncion", "")}')
        print(f'  fal_nombre: {data.get("fal_nombre", "")}')
        print(f'  fal_run: {data.get("fal_run", "")}')
        
        # 2. Crear o actualizar representante en tabla específica
        cur.execute("""
            INSERT INTO app.representante (expediente_id, rep_rut, rep_calidad, rep_nombre, rep_apellido_p, rep_apellido_m, rep_telefono, rep_direccion, rep_comuna, rep_region, rep_email)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (rep_rut) DO UPDATE SET
                expediente_id = EXCLUDED.expediente_id,
                rep_calidad = EXCLUDED.rep_calidad,
                rep_nombre = EXCLUDED.rep_nombre,
                rep_apellido_p = EXCLUDED.rep_apellido_p,
                rep_apellido_m = EXCLUDED.rep_apellido_m,
                rep_telefono = EXCLUDED.rep_telefono,
                rep_direccion = EXCLUDED.rep_direccion,
                rep_comuna = EXCLUDED.rep_comuna,
                rep_region = EXCLUDED.rep_region,
                rep_email = EXCLUDED.rep_email,
                actualizado_en = NOW()
            RETURNING rep_rut
        """, (
            expediente_id,
            data.get('rep_run') or None,
            data.get('rep_calidad') or None,
            data.get('rep_nombre') or None,
            data.get('rep_apellido_p') or None,
            data.get('rep_apellido_m') or None,
            data.get('rep_telefono') or None,
            data.get('rep_direccion') or None,
            data.get('rep_comuna') or None,
            data.get('rep_region') or None,
            data.get('rep_email') or None
        ))
        representante_rut = cur.fetchone()[0]
        
        # 3. Crear o actualizar causante en tabla específica
        cur.execute("""
            INSERT INTO app.causante (expediente_id, fal_run, fal_nacionalidad, fal_nombre, fal_apellido_p, fal_apellido_m, fal_fecha_defuncion, fal_comuna_defuncion, motivo_solicitud)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (fal_run) DO UPDATE SET
                expediente_id = EXCLUDED.expediente_id,
                fal_nacionalidad = EXCLUDED.fal_nacionalidad,
                fal_nombre = EXCLUDED.fal_nombre,
                fal_apellido_p = EXCLUDED.fal_apellido_p,
                fal_apellido_m = EXCLUDED.fal_apellido_m,
                fal_fecha_defuncion = EXCLUDED.fal_fecha_defuncion,
                fal_comuna_defuncion = EXCLUDED.fal_comuna_defuncion,
                motivo_solicitud = EXCLUDED.motivo_solicitud,
                actualizado_en = NOW()
            RETURNING fal_run
        """, (
            expediente_id,
            data.get('fal_run') or None,
            data.get('fal_nacionalidad') or None,
            data.get('fal_nombre') or None,
            data.get('fal_apellido_p') or None,
            data.get('fal_apellido_m') or None,
            data.get('fal_fecha_defuncion') or None,
            data.get('fal_comuna_defuncion') or None,
            data.get('motivo_solicitud') or None
        ))
        causante_run = cur.fetchone()[0]
        
        # 4. Crear solicitud con folio secuencial
        # Obtener el próximo número secuencial para el año actual
        año_actual = datetime.now().year
        
        # Consulta más simple y robusta
        cur.execute("""
            SELECT COALESCE(MAX(
                CASE 
                    WHEN folio ~ ('^SI-\\d{3}-' || %s) THEN 
                        CAST(SUBSTRING(folio FROM 'SI-(\\d{3})-') AS INTEGER)
                    ELSE 0
                END
            ), 0) + 1
            FROM app.solicitudes 
            WHERE folio LIKE ('SI-%%-' || %s)
        """, (año_actual, año_actual))
        
        numero_secuencial = cur.fetchone()[0]
        folio = f"SI-{numero_secuencial:03d}-{año_actual}"
        
        print(f'🔢 Generando folio: {folio} (número secuencial: {numero_secuencial})')
        cur.execute("""
            INSERT INTO app.solicitudes (expediente_id, folio, estado, sucursal, observacion, representante_rut, causante_rut, fecha_defuncion, comuna_fallecimiento)
            VALUES (%s, %s, 'borrador', %s, %s, %s, %s, %s, %s)
            RETURNING id
        """, (
            expediente_id, folio, data.get('sucursal') or None, data.get('motivo_solicitud') or None,
            representante_rut, causante_run, data.get('fal_fecha_defuncion') or None, data.get('fal_comuna_defuncion') or None
        ))
        solicitud_id = cur.fetchone()[0]
        
        print(f'📋 Solicitud creada - ID: {solicitud_id}, Folio: {folio}')
        
        # 5. Crear beneficiarios en tabla específica
        beneficiarios = data.get('beneficiarios', [])
        if beneficiarios and isinstance(beneficiarios, list):
            for beneficiario in beneficiarios:
                if beneficiario.get('nombre') and beneficiario.get('run'):
                    cur.execute("""
                        INSERT INTO app.beneficiarios (expediente_id, solicitud_id, ben_nombre, ben_run, ben_parentesco, es_representante)
                        VALUES (%s, %s, %s, %s, %s, %s)
                        RETURNING id
                    """, (
                        expediente_id, solicitud_id, beneficiario.get('nombre'),
                        beneficiario.get('run'), beneficiario.get('parentesco') or None,
                        beneficiario.get('es_representante', False)
                    ))
        
        # 6. Crear documentos (simplificado)
        tipo_documento = data.get('tipo_documento')
        if tipo_documento:
            cur.execute("""
                INSERT INTO app.documentos_saldo_insoluto (expediente_id, solicitud_id, doc_tipo_id, doc_nombre_archivo, doc_estado)
                VALUES (%s, %s, %s, %s, 'pendiente')
                RETURNING id
            """, (expediente_id, solicitud_id, 1, f"documento_{solicitud_id}"))
        
        # 7. Crear validación
        cur.execute("""
            INSERT INTO app.validacion (expediente_id, solicitud_id, val_sucursal, val_estado)
            VALUES (%s, %s, %s, 'pendiente')
            RETURNING id
        """, (expediente_id, solicitud_id, data.get('sucursal') or None))
        
        # Confirmar transacción
        cur.execute('COMMIT')
        
        # Respuesta exitosa
        response = {
            'success': True,
            'message': 'Solicitud creada exitosamente',
            'data': {
                'expediente_id': expediente_id,
                'expediente_numero': expediente_numero,
                'solicitud_id': solicitud_id,
                'folio': folio,
                'estado': 'borrador'
            }
        }
        
        print(f'📤 Enviando respuesta: {response}')
        
        cur.close()
        conn.close()
        return jsonify(response), 201
        
    except Exception as e:
        # Rollback en caso de error
        cur.execute('ROLLBACK')
        print(f'❌ Error creando solicitud: {e}')
        cur.close()
        conn.close()
        return jsonify({'error': f'Error interno del servidor: {str(e)}'}), 500

@app.route('/api/solicitudes/<int:solicitud_id>/firma-representante', methods=['POST'])
def firmar_representante(solicitud_id):
    """Firmar como representante"""
    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Error de conexión a la base de datos'}), 500
    
    try:
        cur = conn.cursor()
        data = request.get_json()
        
        # Crear firma HMAC-SHA256
        payload = json.dumps(data.get('payload', {}), sort_keys=True)
        clave = data.get('clave', '')
        salt = data.get('salt', '')
        
        # Generar firma
        firma_data = {
            'firma': hmac.new(
                clave.encode('utf-8'),
                (payload + salt).encode('utf-8'),
                hashlib.sha256
            ).hexdigest(),
            'timestamp': datetime.now().isoformat(),
            'solicitud_id': solicitud_id
        }
        
        # Actualizar validación
        cur.execute("""
            UPDATE app.validacion 
            SET val_firma_representante = %s
            WHERE solicitud_id = %s
        """, (json.dumps(firma_data), solicitud_id))
        
        conn.commit()
        cur.close()
        conn.close()
        
        return jsonify({'success': True, 'message': 'Firma de representante guardada'}), 200
        
    except Exception as e:
        print(f'❌ Error firmando representante: {e}')
        cur.close()
        conn.close()
        return jsonify({'error': f'Error interno del servidor: {str(e)}'}), 500

@app.route('/api/solicitudes/<int:solicitud_id>/firma-funcionario', methods=['POST'])
def firmar_funcionario(solicitud_id):
    """Firmar como funcionario"""
    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Error de conexión a la base de datos'}), 500
    
    try:
        cur = conn.cursor()
        data = request.get_json()
        
        # Crear firma HMAC-SHA256
        payload = json.dumps(data.get('payload', {}), sort_keys=True)
        clave = data.get('clave', '')
        salt = data.get('salt', '')
        
        # Generar firma
        firma_data = {
            'firma': hmac.new(
                clave.encode('utf-8'),
                (payload + salt).encode('utf-8'),
                hashlib.sha256
            ).hexdigest(),
            'timestamp': datetime.now().isoformat(),
            'solicitud_id': solicitud_id
        }
        
        # Actualizar validación
        cur.execute("""
            UPDATE app.validacion 
            SET val_firma_funcionario = %s
            WHERE solicitud_id = %s
        """, (json.dumps(firma_data), solicitud_id))
        
        conn.commit()
        cur.close()
        conn.close()
        
        return jsonify({'success': True, 'message': 'Firma de funcionario guardada'}), 200
        
    except Exception as e:
        print(f'❌ Error firmando funcionario: {e}')
        cur.close()
        conn.close()
        return jsonify({'error': f'Error interno del servidor: {str(e)}'}), 500

@app.route('/api/expediente/<int:expediente_id>', methods=['GET'])
def obtener_expediente(expediente_id):
    """Obtener un expediente completo con todos sus datos"""
    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Error de conexión a la base de datos'}), 500
    
    try:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        # Obtener expediente
        cur.execute("SELECT * FROM app.expediente WHERE id = %s", (expediente_id,))
        expediente = cur.fetchone()
        
        if not expediente:
            return jsonify({'error': 'Expediente no encontrado'}), 404
        
        # Obtener representante
        cur.execute("SELECT * FROM app.representante WHERE expediente_id = %s", (expediente_id,))
        representante = cur.fetchone()
        
        # Obtener causante
        cur.execute("SELECT * FROM app.causante WHERE expediente_id = %s", (expediente_id,))
        causante = cur.fetchone()
        
        # Obtener solicitudes
        cur.execute("SELECT * FROM app.solicitudes WHERE expediente_id = %s", (expediente_id,))
        solicitudes = cur.fetchall()
        
        # Obtener beneficiarios
        cur.execute("SELECT * FROM app.beneficiarios WHERE expediente_id = %s", (expediente_id,))
        beneficiarios = cur.fetchall()
        
        # Obtener documentos
        cur.execute("SELECT * FROM app.documentos_saldo_insoluto WHERE expediente_id = %s", (expediente_id,))
        documentos = cur.fetchall()
        
        # Obtener validación
        cur.execute("SELECT * FROM app.validacion WHERE expediente_id = %s", (expediente_id,))
        validacion = cur.fetchone()
        
        # Construir respuesta
        response = {
            'expediente': dict(expediente) if expediente else None,
            'representante': dict(representante) if representante else None,
            'causante': dict(causante) if causante else None,
            'solicitudes': [dict(s) for s in solicitudes],
            'beneficiarios': [dict(b) for b in beneficiarios],
            'documentos': [dict(d) for d in documentos],
            'validacion': dict(validacion) if validacion else None
        }
        
        cur.close()
        conn.close()
        return jsonify(response), 200
        
    except Exception as e:
        print(f'❌ Error obteniendo expediente: {e}')
        cur.close()
        conn.close()
        return jsonify({'error': f'Error interno del servidor: {str(e)}'}), 500

@app.route('/api/upload-documento', methods=['POST'])
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
        
        # Verificar si ya existe un archivo con el mismo hash
        cur.execute("""
            SELECT id FROM app.documentos_saldo_insoluto 
            WHERE doc_sha256 = %s
        """, (file_hash,))
        
        existing_doc = cur.fetchone()
        if existing_doc:
            return jsonify({
                'error': 'Ya existe un archivo idéntico en el sistema',
                'documento_id': existing_doc[0]
            }), 409
        
        # Obtener expediente_id de la solicitud
        cur.execute("""
            SELECT expediente_id FROM app.solicitudes WHERE id = %s
        """, (solicitud_id,))
        
        expediente_result = cur.fetchone()
        if not expediente_result:
            return jsonify({'error': 'Solicitud no encontrada'}), 404
        
        expediente_id = expediente_result[0]
        
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
            mime_type, len(file_data), file_hash, f"/api/download-documento/{{id}}", observaciones
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

@app.route('/api/usuarios', methods=['POST'])
def crear_usuario():
    """Crear un nuevo usuario funcionario"""
    print("🔔 Petición recibida en /api/usuarios")
    print(f"📥 Datos recibidos: {request.get_json()}")
    
    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Error de conexión a la base de datos'}), 500
    
    try:
        data = request.get_json()
        
        # Validar datos requeridos
        required_fields = ['nombres', 'apellido_p', 'rut', 'email', 'rol', 'password', 'password_confirm']
        for field in required_fields:
            if not data.get(field):
                return jsonify({'error': f'Campo requerido: {field}'}), 400
        
        # Validar sucursal si se proporciona
        sucursal = data.get('sucursal', '').strip()
        if sucursal and sucursal not in ['providencia', 'nunoa', 'santo_domingo']:
            return jsonify({'error': 'Sucursal no válida'}), 400
        
        # Validar que las contraseñas coincidan
        if data['password'] != data['password_confirm']:
            return jsonify({'error': 'Las contraseñas no coinciden'}), 400
        
        # Validar RUT chileno
        print(f"🔍 RUT recibido: '{data['rut']}'")
        print(f"🔍 Tipo de RUT: {type(data['rut'])}")
        print(f"🔍 Longitud RUT: {len(data['rut'])}")
        
        if not validar_rut_chileno(data['rut']):
            print(f"❌ RUT inválido: '{data['rut']}'")
            return jsonify({'error': 'RUT inválido'}), 400
        else:
            print(f"✅ RUT válido: '{data['rut']}'")
        
        # Validar email
        import re
        email_pattern = r'^[^\s@]+@[^\s@]+\.[^\s@]+$'
        if not re.match(email_pattern, data['email']):
            return jsonify({'error': 'Formato de email inválido'}), 400
        
        # Validar rol
        valid_roles = ['ejecutivo_plataforma', 'jefatura']
        if data['rol'] not in valid_roles:
            return jsonify({'error': 'Rol inválido. Debe ser: ejecutivo_plataforma o jefatura'}), 400
        
        # Validar fortaleza de contraseña
        password = data['password']
        if len(password) < 8:
            return jsonify({'error': 'La contraseña debe tener al menos 8 caracteres'}), 400
        
        # Verificar requisitos de contraseña
        has_upper = any(c.isupper() for c in password)
        has_lower = any(c.islower() for c in password)
        has_digit = any(c.isdigit() for c in password)
        has_special = any(c in '!@#$%^&*()_+-=[]{}|;:,.<>?' for c in password)
        
        if not all([has_upper, has_lower, has_digit, has_special]):
            return jsonify({'error': 'La contraseña debe tener mayúsculas, minúsculas, números y símbolos'}), 400
        
        cur = conn.cursor()
        
        # Verificar si el RUT ya existe
        cur.execute("SELECT id FROM app.funcionarios WHERE rut = %s", (data['rut'],))
        if cur.fetchone():
            return jsonify({'error': 'Ya existe un funcionario con este RUT'}), 409
        
        # Verificar si el email ya existe
        cur.execute("SELECT id FROM app.funcionarios WHERE email = %s", (data['email'],))
        if cur.fetchone():
            return jsonify({'error': 'Ya existe un funcionario con este email'}), 409
        
        # Encriptar contraseña
        password_hash = hash_password(password)
        
        # Insertar usuario (las iniciales se generan automáticamente por el trigger)
        cur.execute("""
            INSERT INTO app.funcionarios (rut, nombres, apellido_p, apellido_m, email, password_hash, rol, sucursal)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id, iniciales
        """, (
            data['rut'],
            data['nombres'].strip(),
            data['apellido_p'].strip(),
            data.get('apellido_m', '').strip() or None,
            data['email'].strip().lower(),
            password_hash,
            data['rol'],  # Rol seleccionado desde el frontend
            sucursal if sucursal else 'IPS Central'  # Sucursal seleccionada o por defecto
        ))
        
        result = cur.fetchone()
        usuario_id, iniciales = result
        
        conn.commit()
        cur.close()
        conn.close()
        
        print(f'👤 Usuario creado: {data["nombres"]} {data["apellido_p"]} - Iniciales: {iniciales}')
        
        return jsonify({
            'success': True,
            'message': 'Usuario creado exitosamente',
            'data': {
                'id': usuario_id,
                'rut': data['rut'],
                'nombres': data['nombres'],
                'apellido_p': data['apellido_p'],
                'apellido_m': data.get('apellido_m'),
                'email': data['email'],
                'iniciales': iniciales,
                'rol': data['rol'],
                'sucursal': sucursal if sucursal else 'IPS Central'
            }
        }), 201
        
    except Exception as e:
        print(f'❌ Error creando usuario: {e}')
        if 'conn' in locals():
            conn.rollback()
            conn.close()
        return jsonify({'error': f'Error interno del servidor: {str(e)}'}), 500

@app.route('/api/health', methods=['GET'])
def health_check():
    """Endpoint de salud del servidor"""
    return jsonify({
        'status': 'OK',
        'message': 'Servidor Flask funcionando correctamente',
        'timestamp': datetime.now().isoformat()
    }), 200

@app.route('/api/login', methods=['POST'])
def login():
    """Autenticar funcionario con RUT y contraseña"""
    print("🔔 Petición de login recibida")
    
    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Error de conexión a la base de datos'}), 500
    
    try:
        data = request.get_json()
        
        # Validar datos requeridos
        if not data.get('rut') or not data.get('password'):
            return jsonify({'error': 'RUT y contraseña son requeridos'}), 400
        
        rut = data['rut'].strip()
        password = data['password']
        
        print(f"🔍 Intentando login con RUT: {rut}")
        
        # Buscar funcionario por RUT
        cur = conn.cursor()
        cur.execute("""
            SELECT id, rut, nombres, apellido_p, apellido_m, password_hash, rol, sucursal, iniciales, activo
            FROM app.funcionarios 
            WHERE rut = %s AND activo = true
        """, (rut,))
        
        funcionario = cur.fetchone()
        
        if not funcionario:
            print(f"❌ Funcionario no encontrado o inactivo: {rut}")
            return jsonify({'error': 'RUT o contraseña incorrectos'}), 401
        
        # Verificar contraseña
        stored_hash = funcionario[5]  # password_hash
        if not bcrypt.checkpw(password.encode('utf-8'), stored_hash.encode('utf-8')):
            print(f"❌ Contraseña incorrecta para RUT: {rut}")
            return jsonify({'error': 'RUT o contraseña incorrectos'}), 401
        
        # Login exitoso
        print(f"✅ Login exitoso para: {funcionario[2]} {funcionario[3]} ({rut})")
        
        return jsonify({
            'success': True,
            'message': 'Login exitoso',
            'data': {
                'id': funcionario[0],
                'rut': funcionario[1],
                'nombres': funcionario[2],
                'apellido_p': funcionario[3],
                'apellido_m': funcionario[4],
                'rol': funcionario[6],
                'sucursal': funcionario[7],
                'iniciales': funcionario[8]
            }
        }), 200
        
    except Exception as e:
        print(f'❌ Error en login: {e}')
        if 'conn' in locals():
            conn.rollback()
            conn.close()
        return jsonify({'error': f'Error interno del servidor: {str(e)}'}), 500

if __name__ == '__main__':
    if test_connection():
        config = Config()
        print(f'✅ Servidor Flask ejecutándose en puerto {config.PORT}')
        print(f'🔗 URL: http://localhost:{config.PORT}')
        app.run(host=config.HOST, port=config.PORT, debug=config.DEBUG)
    else:
        print('❌ No se pudo conectar a la base de datos')
