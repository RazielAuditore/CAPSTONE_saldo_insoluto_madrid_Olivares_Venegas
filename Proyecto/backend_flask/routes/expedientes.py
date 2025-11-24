"""
Rutas de gestión de expedientes
"""
from flask import request, jsonify
from psycopg2.extras import RealDictCursor
from utils.database import get_db_connection
from middleware.auth import login_required

def register_routes(app):
    """Registrar rutas de expedientes"""
    
    @app.route('/api/expediente/<int:expediente_id>', methods=['GET'])
    def obtener_expediente(expediente_id):
        """Obtener un expediente completo con todos sus datos"""
        conn = get_db_connection()
        if not conn:
            return jsonify({'error': 'Error de conexión a la base de datos'}), 500
        
        try:
            cur = conn.cursor(cursor_factory=RealDictCursor)
            
            cur.execute("SELECT * FROM app.expediente WHERE id = %s", (expediente_id,))
            expediente = cur.fetchone()
            
            if not expediente:
                return jsonify({'error': 'Expediente no encontrado'}), 404
            
            cur.execute("SELECT * FROM app.representante WHERE expediente_id = %s", (expediente_id,))
            representante = cur.fetchone()
            
            cur.execute("SELECT * FROM app.causante WHERE expediente_id = %s", (expediente_id,))
            causante = cur.fetchone()
            
            cur.execute("SELECT * FROM app.solicitudes WHERE expediente_id = %s", (expediente_id,))
            solicitudes = cur.fetchall()
            
            cur.execute("SELECT * FROM app.beneficiarios WHERE expediente_id = %s", (expediente_id,))
            beneficiarios = cur.fetchall()
            
            cur.execute("SELECT * FROM app.documentos_saldo_insoluto WHERE expediente_id = %s", (expediente_id,))
            documentos = cur.fetchall()
            
            cur.execute("SELECT * FROM app.validacion WHERE expediente_id = %s", (expediente_id,))
            validacion = cur.fetchone()
            
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
            cur.close()
            conn.close()
            return jsonify({'error': f'Error interno del servidor: {str(e)}'}), 500


    @app.route('/api/beneficiarios/<int:beneficiario_id>', methods=['DELETE'])
    @login_required
    def eliminar_beneficiario(beneficiario_id):
        """Eliminar un beneficiario"""
        conn = get_db_connection()
        if not conn:
            return jsonify({'error': 'Error de conexión a la base de datos'}), 500
        
        try:
            cur = conn.cursor()
            
          
            cur.execute("""
                SELECT b.id, b.expediente_id, s.estado
                FROM app.beneficiarios b
                JOIN app.solicitudes s ON b.expediente_id = s.expediente_id
                WHERE b.id = %s
                ORDER BY s.id DESC LIMIT 1
            """, (beneficiario_id,))
            
            beneficiario = cur.fetchone()
            if not beneficiario:
                cur.close()
                conn.close()
                return jsonify({'error': 'Beneficiario no encontrado'}), 404
            
            estado = beneficiario[2]
            if estado != 'rechazado/enRevision':
                cur.close()
                conn.close()
                return jsonify({'error': 'Solo se pueden eliminar beneficiarios de expedientes rechazados en revisión'}), 400
            
        
            cur.execute("DELETE FROM app.beneficiarios WHERE id = %s", (beneficiario_id,))
            
            conn.commit()
            cur.close()
            conn.close()
            
            return jsonify({
                'success': True,
                'message': 'Beneficiario eliminado exitosamente'
            }), 200
            
        except Exception as e:
            print(f'❌ Error eliminando beneficiario: {e}')
            if 'conn' in locals():
                conn.rollback()
                conn.close()
            return jsonify({'error': f'Error interno del servidor: {str(e)}'}), 500

    @app.route('/api/revision-expediente', methods=['POST'])
    @login_required
    def revision_expediente():
        """Buscar expediente por RUT del causante para revisión"""
        conn = get_db_connection()
        if not conn:
            return jsonify({'error': 'Error de conexión a la base de datos'}), 500
        
        try:
            data = request.get_json()
            
            if not data or not data.get('rut'):
                return jsonify({'error': 'RUT es requerido'}), 400
            
            rut = data['rut'].strip()
            rut_limpio = rut.replace('.', '').replace('-', '').upper()
            
            if len(rut_limpio) < 8 or len(rut_limpio) > 9:
                return jsonify({'error': 'Formato de RUT inválido'}), 400
            
            cur = conn.cursor(cursor_factory=RealDictCursor)
            
        
            cur.execute("""
                SELECT app.expediente.id as expediente_id
                FROM app.expediente
                JOIN app.causante ON app.expediente.id = app.causante.expediente_id
                WHERE app.causante.fal_run = %s
                ORDER BY app.expediente.id DESC
                LIMIT 1
            """, (rut,))
            
            expediente_row = cur.fetchone()
            
            if not expediente_row:
                cur.close()
                conn.close()
                return jsonify({
                    'success': True,
                    'data': {
                        'expediente_id': None,
                        'rut': rut
                    }
                }), 200
            
            expediente_id = expediente_row['expediente_id']
            
            # Obtener datos del expediente
            cur.execute("SELECT * FROM app.expediente WHERE id = %s", (expediente_id,))
            expediente = cur.fetchone()
            
            # Obtener datos del causante
            cur.execute("SELECT * FROM app.causante WHERE expediente_id = %s", (expediente_id,))
            causante = cur.fetchone()
            
            # Obtener datos del representante
            cur.execute("SELECT * FROM app.representante WHERE expediente_id = %s", (expediente_id,))
            representante = cur.fetchone()
            
            # Obtener solicitud más reciente (ordenar por id DESC para obtener la más reciente)
            cur.execute("""
                SELECT * FROM app.solicitudes 
                WHERE expediente_id = %s 
                ORDER BY id DESC 
                LIMIT 1
            """, (expediente_id,))
            solicitud = cur.fetchone()
            
            # Obtener funcionario
            funcionario = None
            if expediente.get('funcionario_id'):
                cur.execute("SELECT * FROM app.funcionarios WHERE id = %s", (expediente['funcionario_id'],))
                funcionario = cur.fetchone()
            
            # Obtener beneficiarios
            cur.execute("""
                SELECT 
                    id,
                    ben_nombre,
                    ben_run,
                    ben_parentesco,
                    es_representante
                FROM app.beneficiarios
                WHERE expediente_id = %s
                ORDER BY id
            """, (expediente_id,))
            
            beneficiarios = cur.fetchall()
            
            # Obtener documentos
            cur.execute("""
                SELECT 
                    id,
                    doc_tipo_id,
                    doc_nombre_archivo as nombre_archivo,
                    doc_ruta_storage as ruta_archivo,
                    doc_mime_type as mime_type,
                    doc_tamano_bytes as tamano_bytes,
                    doc_fecha_subida as fecha_subida
                FROM app.documentos_saldo_insoluto
                WHERE expediente_id = %s
                ORDER BY doc_fecha_subida DESC NULLS LAST
            """, (expediente_id,))
            
            documentos = cur.fetchall()
            
            # Obtener validación
            cur.execute("""
                SELECT 
                    id,
                    funcionario_firmado,
                    funcionario_firma_hex,
                    funcionario_firma_salt_hex,
                    funcionario_firma_algoritmo,
                    funcionario_firma_ts,
                    funcionario_id as validacion_funcionario_id
                FROM app.validacion
                WHERE expediente_id = %s
            """, (expediente_id,))
            
            validacion = cur.fetchone()
            
            # Construir respuesta
            response_data = {
                'expediente_id': expediente['id'],
                'expediente_numero': expediente['expediente_numero'],
                'estado_expediente': expediente['estado'],
                'observaciones': expediente['observaciones'],
                'fecha_creacion': expediente['fecha_creacion'].isoformat() if expediente.get('fecha_creacion') else None,
                'causante': {
                    'id': causante['id'],
                    'fal_run': causante['fal_run'],
                    'fal_nombre': causante['fal_nombre'],
                    'fal_apellido_p': causante['fal_apellido_p'],
                    'fal_apellido_m': causante['fal_apellido_m'],
                    'fal_nacionalidad': causante['fal_nacionalidad'],
                    'fal_fecha_defuncion': causante['fal_fecha_defuncion'].isoformat() if causante.get('fal_fecha_defuncion') else None,
                    'fal_comuna_defuncion': causante['fal_comuna_defuncion']
                } if causante else None,
                'representante': {
                    'id': representante['id'],
                    'rep_run': representante['rep_rut'],
                    'rep_calidad': representante['rep_calidad'],
                    'rep_nombre': representante['rep_nombre'],
                    'rep_apellido_p': representante['rep_apellido_p'],
                    'rep_apellido_m': representante['rep_apellido_m'],
                    'rep_telefono': representante['rep_telefono'],
                    'rep_direccion': representante['rep_direccion'],
                    'rep_comuna': representante['rep_comuna'],
                    'rep_region': representante['rep_region'],
                    'rep_email': representante['rep_email']
                } if representante else None,
                'solicitud': {
                    'id': solicitud['id'],
                    'folio': solicitud['folio'],
                    'estado': solicitud['estado'],
                    'monto_solicitado': float(solicitud['monto_solicitado']) if solicitud.get('monto_solicitado') else None,
                    'sucursal': solicitud['sucursal'],
                    'fecha_creacion': solicitud['fecha_creacion'].isoformat() if solicitud.get('fecha_creacion') else None
                } if solicitud else None,
                'funcionario': {
                    'id': funcionario['id'],
                    'rut': funcionario['rut'],
                    'nombres': funcionario['nombres'],
                    'apellido_p': funcionario['apellido_p'],
                    'apellido_m': funcionario['apellido_m']
                } if funcionario else None,
                'beneficiarios': [dict(b) for b in beneficiarios],
                'documentos': [dict(d) for d in documentos],
                'validacion': dict(validacion) if validacion else None
            }
            
            cur.close()
            conn.close()
            
            return jsonify({
                'success': True,
                'data': response_data
            }), 200
            
        except Exception as e:
            print(f'❌ Error en revision_expediente: {e}')
            import traceback
            print(traceback.format_exc())
            if 'conn' in locals():
                conn.close()
            return jsonify({'error': f'Error interno del servidor: {str(e)}'}), 500


