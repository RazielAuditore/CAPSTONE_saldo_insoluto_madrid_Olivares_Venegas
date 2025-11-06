"""
Rutas de gestión de solicitudes
"""
from flask import request, jsonify, session
from datetime import datetime
import json
import hmac
import hashlib
from psycopg2.extras import RealDictCursor
from utils.database import get_db_connection
from routes.auth import login_required

def register_routes(app):
    """Registrar rutas de solicitudes"""
    
    @app.route('/api/solicitudes', methods=['POST'])
    @login_required
    def crear_solicitud():
        """Crear una nueva solicitud de saldo insoluto"""
        conn = get_db_connection()
        if not conn:
            return jsonify({'error': 'Error de conexión a la base de datos'}), 500
        
        try:
            cur = conn.cursor()
            cur.execute('BEGIN')
            
            expediente_numero = f"EXP-{datetime.now().year}-{datetime.now().strftime('%H%M%S')}"
            funcionario_id = session.get('user_id', 1)
            
            cur.execute("""
                INSERT INTO app.expediente (expediente_numero, estado, observaciones, funcionario_id)
                VALUES (%s, 'en_proceso', 'Expediente de saldo insoluto creado automáticamente', %s)
                RETURNING id
            """, (expediente_numero, funcionario_id))
            expediente_id = cur.fetchone()[0]
            
            data = request.get_json()
            
            # Representante
            cur.execute("""
                INSERT INTO app.representante (expediente_id, rep_rut, rep_calidad, rep_nombre, rep_apellido_p, rep_apellido_m, rep_telefono, rep_direccion, rep_comuna, rep_region, rep_email)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (rep_rut) DO UPDATE SET expediente_id = EXCLUDED.expediente_id
                RETURNING rep_rut
            """, (
                expediente_id, data.get('rep_run') or None, data.get('rep_calidad') or None,
                data.get('rep_nombre') or None, data.get('rep_apellido_p') or None,
                data.get('rep_apellido_m') or None, data.get('rep_telefono') or None,
                data.get('rep_direccion') or None, data.get('rep_comuna') or None,
                data.get('rep_region') or None, data.get('rep_email') or None
            ))
            representante_rut = cur.fetchone()[0]
            
            # Causante
            cur.execute("""
                INSERT INTO app.causante (expediente_id, fal_run, fal_nacionalidad, fal_nombre, fal_apellido_p, fal_apellido_m, fal_fecha_defuncion, fal_comuna_defuncion, motivo_solicitud)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (fal_run) DO UPDATE SET expediente_id = EXCLUDED.expediente_id
                RETURNING fal_run
            """, (
                expediente_id, data.get('fal_run') or None, data.get('fal_nacionalidad') or None,
                data.get('fal_nombre') or None, data.get('fal_apellido_p') or None,
                data.get('fal_apellido_m') or None, data.get('fal_fecha_defuncion') or None,
                data.get('fal_comuna_defuncion') or None, data.get('motivo_solicitud') or None
            ))
            causante_run = cur.fetchone()[0]
            
            # Solicitud
            año_actual = datetime.now().year
            cur.execute("""
                SELECT COALESCE(MAX(CASE WHEN folio ~ ('^SI-\\d{3}-' || %s) 
                THEN CAST(SUBSTRING(folio FROM 'SI-(\\d{3})-') AS INTEGER) ELSE 0 END), 0) + 1
                FROM app.solicitudes WHERE folio LIKE ('SI-%%-' || %s)
            """, (año_actual, año_actual))
            numero_secuencial = cur.fetchone()[0]
            folio = f"SI-{numero_secuencial:03d}-{año_actual}"
            
            cur.execute("""
                INSERT INTO app.solicitudes (expediente_id, folio, estado, sucursal, observacion, representante_rut, causante_rut, fecha_defuncion, comuna_fallecimiento)
                VALUES (%s, %s, 'borrador', %s, %s, %s, %s, %s, %s)
                RETURNING id
            """, (
                expediente_id, folio, data.get('sucursal') or None, data.get('motivo_solicitud') or None,
                representante_rut, causante_run, data.get('fal_fecha_defuncion') or None,
                data.get('fal_comuna_defuncion') or None
            ))
            solicitud_id = cur.fetchone()[0]
            
            # Beneficiarios
            beneficiarios = data.get('beneficiarios', [])
            if beneficiarios and isinstance(beneficiarios, list):
                for beneficiario in beneficiarios:
                    if beneficiario.get('nombre') and beneficiario.get('run'):
                        cur.execute("""
                            INSERT INTO app.beneficiarios (expediente_id, solicitud_id, ben_nombre, ben_run, ben_parentesco, es_representante)
                            VALUES (%s, %s, %s, %s, %s, %s)
                        """, (
                            expediente_id, solicitud_id, beneficiario.get('nombre'),
                            beneficiario.get('run'), beneficiario.get('parentesco') or None,
                            beneficiario.get('es_representante', False)
                        ))
            
            # Validación
            cur.execute("""
                INSERT INTO app.validacion (expediente_id, solicitud_id, val_sucursal, val_estado)
                VALUES (%s, %s, %s, 'pendiente')
            """, (expediente_id, solicitud_id, data.get('sucursal') or None))
            
            cur.execute('COMMIT')
            cur.close()
            conn.close()
            
            return jsonify({
                'success': True,
                'message': 'Solicitud creada exitosamente',
                'data': {
                    'expediente_id': expediente_id,
                    'expediente_numero': expediente_numero,
                    'solicitud_id': solicitud_id,
                    'folio': folio,
                    'estado': 'borrador'
                }
            }), 201
            
        except Exception as e:
            cur.execute('ROLLBACK')
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
            
            payload = json.dumps(data.get('payload', {}), sort_keys=True)
            clave = data.get('clave', '')
            salt = data.get('salt', '')
            
            firma_data = {
                'firma': hmac.new(
                    clave.encode('utf-8'),
                    (payload + salt).encode('utf-8'),
                    hashlib.sha256
                ).hexdigest(),
                'timestamp': datetime.now().isoformat(),
                'solicitud_id': solicitud_id
            }
            
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
            
            payload = json.dumps(data.get('payload', {}), sort_keys=True)
            clave = data.get('clave', '')
            salt = data.get('salt', '')
            
            firma_data = {
                'firma': hmac.new(
                    clave.encode('utf-8'),
                    (payload + salt).encode('utf-8'),
                    hashlib.sha256
                ).hexdigest(),
                'timestamp': datetime.now().isoformat(),
                'solicitud_id': solicitud_id
            }
            
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
            cur.close()
            conn.close()
            return jsonify({'error': f'Error interno del servidor: {str(e)}'}), 500

    @app.route('/api/solicitudes/<int:solicitud_id>/firmar-funcionario', methods=['POST'])
    @login_required
    def firmar_solicitud_funcionario(solicitud_id):
        """Firmar solicitud como funcionario"""
        conn = get_db_connection()
        if not conn:
            return jsonify({'error': 'Error de conexión a la base de datos'}), 500
        
        try:
            data = request.get_json()
            
            if not data.get('firma_data'):
                return jsonify({'error': 'Datos de firma requeridos'}), 400
            
            firma_data = data['firma_data']
            cur = conn.cursor()
            
            cur.execute("SELECT id, expediente_id FROM app.solicitudes WHERE id = %s", (solicitud_id,))
            solicitud = cur.fetchone()
            
            if not solicitud:
                return jsonify({'error': 'Solicitud no encontrada'}), 404
            
            expediente_id = solicitud[1]
            
            cur.execute("""
                UPDATE app.validacion 
                SET val_firma_funcionario = %s, val_estado = 'firmado_funcionario', val_fecha_firma_funcionario = NOW()
                WHERE solicitud_id = %s
            """, (json.dumps(firma_data), solicitud_id))
            
            cur.execute("UPDATE app.solicitudes SET estado = 'firmado_funcionario' WHERE id = %s", (solicitud_id,))
            
            conn.commit()
            cur.close()
            conn.close()
            
            return jsonify({
                'success': True,
                'message': 'Solicitud firmada por funcionario exitosamente',
                'data': {
                    'solicitud_id': solicitud_id,
                    'expediente_id': expediente_id,
                    'estado': 'firmado_funcionario'
                }
            }), 200
            
        except Exception as e:
            if 'conn' in locals():
                conn.rollback()
                conn.close()
            return jsonify({'error': f'Error interno del servidor: {str(e)}'}), 500


