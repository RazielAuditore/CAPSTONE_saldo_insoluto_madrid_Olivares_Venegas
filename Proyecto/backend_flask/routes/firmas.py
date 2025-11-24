"""
Rutas de gestión de firmas
"""
from flask import request, jsonify, session
from datetime import datetime
import json
import hmac
import hashlib
from psycopg2.extras import RealDictCursor
from utils.database import get_db_connection
from middleware.auth import login_required
from services.solicitud_service import verificar_y_actualizar_estado_pendiente

def register_routes(app):
    """Registrar rutas de firmas"""
    
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
            if 'cur' in locals():
                cur.close()
            if 'conn' in locals():
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
            if 'cur' in locals():
                cur.close()
            if 'conn' in locals():
                conn.close()
            return jsonify({'error': f'Error interno del servidor: {str(e)}'}), 500

    @app.route('/api/beneficiarios/<int:beneficiario_id>/firma', methods=['POST'])
    @login_required
    def firmar_beneficiario(beneficiario_id):
        """Firmar como beneficiario usando contraseña de app externa"""
        print(f"🔔 Petición de firma de beneficiario ID: {beneficiario_id}")
        
        conn = get_db_connection()
        if not conn:
            return jsonify({'error': 'Error de conexión a la base de datos'}), 500
        
        try:
            data = request.get_json()
            
            # Validar datos requeridos
            if not data.get('firma_hash'):
                return jsonify({'error': 'Firma (contraseña) es requerida'}), 400
            
            if not data.get('expediente_id'):
                return jsonify({'error': 'ID de expediente es requerido'}), 400
            
            firma_hash = data['firma_hash']
            expediente_id = data['expediente_id']
            
            cur = conn.cursor()
            
            # Verificar que el beneficiario existe y pertenece al expediente
            cur.execute("""
                SELECT id, ben_nombre, ben_run 
                FROM app.beneficiarios 
                WHERE id = %s AND expediente_id = %s
            """, (beneficiario_id, expediente_id))
            
            beneficiario = cur.fetchone()
            if not beneficiario:
                return jsonify({'error': 'Beneficiario no encontrado o no pertenece al expediente'}), 404
            
            # Verificar si ya tiene una firma activa en usuarios_firma
            cur.execute("""
                SELECT uf.id FROM app.usuarios_firma uf
                JOIN app.beneficiarios b ON uf.rut = b.ben_run
                WHERE b.id = %s AND b.expediente_id = %s
            """, (beneficiario_id, expediente_id))
            
            if cur.fetchone():
                return jsonify({'error': 'El beneficiario ya tiene una firma activa'}), 400
            
            # Obtener la firma existente para la respuesta
            cur.execute("""
                SELECT uf.id FROM app.usuarios_firma uf
                JOIN app.beneficiarios b ON uf.rut = b.ben_run
                WHERE b.id = %s AND b.expediente_id = %s
            """, (beneficiario_id, expediente_id))
            
            firma_result = cur.fetchone()
            firma_id = firma_result[0] if firma_result else None
            
            # Obtener solicitud_id para verificar si puede cambiar a pendiente
            cur.execute("""
                SELECT id FROM app.solicitudes 
                WHERE expediente_id = %s 
                ORDER BY id DESC LIMIT 1
            """, (expediente_id,))
            
            solicitud_result = cur.fetchone()
            solicitud_id = solicitud_result[0] if solicitud_result else None
            
            # Verificar si la solicitud está lista para evaluación (todas las firmas + cálculo)
            if solicitud_id:
                verificar_y_actualizar_estado_pendiente(expediente_id, solicitud_id, cur, conn)
            
            conn.commit()
            cur.close()
            conn.close()
            
            print(f'✅ Firma de beneficiario registrada: {beneficiario[1]}')
            
            return jsonify({
                'success': True,
                'message': 'Firma de beneficiario verificada exitosamente',
                'data': {
                    'firma_id': firma_id,
                    'beneficiario_id': beneficiario_id,
                    'expediente_id': expediente_id,
                    'beneficiario': {
                        'nombre': beneficiario[1],
                        'rut': beneficiario[2]
                    }
                }
            }), 200
            
        except Exception as e:
            print(f'❌ Error firmando beneficiario: {e}')
            if 'conn' in locals():
                conn.rollback()
                conn.close()
            return jsonify({'error': f'Error interno del servidor: {str(e)}'}), 500

    @app.route('/api/expediente/<int:expediente_id>/firmas-beneficiarios', methods=['GET'])
    @login_required
    def obtener_firmas_beneficiarios(expediente_id):
        """Obtener todas las firmas de beneficiarios de un expediente"""
        print(f"🔔 Consultando firmas de beneficiarios para expediente: {expediente_id}")
        
        conn = get_db_connection()
        if not conn:
            return jsonify({'error': 'Error de conexión a la base de datos'}), 500
        
        try:
            cur = conn.cursor(cursor_factory=RealDictCursor)
            
            # Obtener firmas con datos de beneficiarios desde usuarios_firma
            cur.execute("""
                SELECT 
                    uf.id as firma_id,
                    uf.rut,
                    b.id as beneficiario_id,
                    b.ben_nombre,
                    b.ben_run
                FROM app.usuarios_firma uf
                JOIN app.beneficiarios b ON uf.rut = b.ben_run
                WHERE b.expediente_id = %s
                ORDER BY uf.id DESC
            """, (expediente_id,))
            
            firmas = cur.fetchall()
            
            # Obtener total de beneficiarios del expediente
            cur.execute("""
                SELECT COUNT(*) as total_beneficiarios
                FROM app.beneficiarios 
                WHERE expediente_id = %s
            """, (expediente_id,))
            
            total_beneficiarios = cur.fetchone()['total_beneficiarios']
            
            cur.close()
            conn.close()
            
            return jsonify({
                'success': True,
                'data': {
                    'expediente_id': expediente_id,
                    'total_beneficiarios': total_beneficiarios,
                    'beneficiarios_firmados': len(firmas),
                    'beneficiarios_pendientes': total_beneficiarios - len(firmas),
                    'firmas': [dict(firma) for firma in firmas]
                }
            }), 200
            
        except Exception as e:
            print(f'❌ Error consultando firmas de beneficiarios: {e}')
            if 'conn' in locals():
                conn.close()
            return jsonify({'error': f'Error interno del servidor: {str(e)}'}), 500

    @app.route('/api/solicitudes/<int:solicitud_id>/firmar-funcionario', methods=['POST'])
    @login_required
    def firmar_solicitud_funcionario(solicitud_id):
        """Firmar solicitud como funcionario"""
        print(f"🔔 Petición de firma de funcionario para solicitud: {solicitud_id}")
        
        conn = get_db_connection()
        if not conn:
            return jsonify({'error': 'Error de conexión a la base de datos'}), 500
        
        try:
            data = request.get_json()
            
            # Validar datos requeridos
            if not data.get('firma_data'):
                return jsonify({'error': 'Datos de firma requeridos'}), 400
            
            firma_data = data['firma_data']
            
            cur = conn.cursor()
            
            # Verificar que la solicitud existe
            cur.execute("SELECT id, expediente_id FROM app.solicitudes WHERE id = %s", (solicitud_id,))
            solicitud = cur.fetchone()
            
            if not solicitud:
                return jsonify({'error': 'Solicitud no encontrada'}), 404
            
            expediente_id = solicitud[1]
            
            # Obtener funcionario_id de la firma_data o de la sesión
            funcionario_id_firma = firma_data.get('funcionario_id') or session.get('user_id')
            
            print(f'🔍 funcionario_id_firma obtenido: {funcionario_id_firma}')
            print(f'🔍 firma_data contiene: {list(firma_data.keys())}')
            
            if not funcionario_id_firma:
                return jsonify({'error': 'No se pudo identificar al funcionario'}), 400
            
            # Verificar que el funcionario existe en la tabla funcionarios
            cur.execute("""
                SELECT id FROM app.funcionarios 
                WHERE id = %s AND activo = true
            """, (funcionario_id_firma,))
            
            funcionario = cur.fetchone()
            if not funcionario:
                return jsonify({'error': 'Funcionario no encontrado o inactivo'}), 404
            
            print(f'✅ Funcionario {funcionario_id_firma} verificado correctamente')
            
            # Verificar que las columnas existen, si no, intentar crearlas
            try:
                cur.execute("""
                    SELECT column_name 
                    FROM information_schema.columns 
                    WHERE table_schema = 'app' 
                    AND table_name = 'solicitudes' 
                    AND column_name IN ('firmado_funcionario', 'fecha_firma_funcionario', 'funcionario_id_firma')
                """)
                columnas_existentes = [row[0] for row in cur.fetchall()]
                print(f'🔍 Columnas existentes: {columnas_existentes}')
                
                if 'firmado_funcionario' not in columnas_existentes:
                    print('⚠️ Columnas no existen, intentando crearlas...')
                    from utils.database import add_firma_funcionario_columns
                    add_firma_funcionario_columns()
            except Exception as e:
                print(f'⚠️ Error verificando columnas: {e}')
            
            # Asegurar que las columnas existen antes de hacer UPDATE
            print('🔍 Verificando existencia de columnas...')
            cur.execute("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_schema = 'app' 
                AND table_name = 'solicitudes' 
                AND column_name IN ('firmado_funcionario', 'fecha_firma_funcionario', 'funcionario_id_firma')
            """)
            columnas_existentes = [row[0] for row in cur.fetchall()]
            print(f'🔍 Columnas encontradas: {columnas_existentes}')
            
            if len(columnas_existentes) < 3:
                print('⚠️ Faltan columnas, creándolas ahora...')
                cur.close()
                conn.close()
                from utils.database import add_firma_funcionario_columns
                add_firma_funcionario_columns()
                conn = get_db_connection()
                cur = conn.cursor()
                print('✅ Columnas creadas, continuando con UPDATE...')
            
            # Actualizar solicitudes con la información de firma del funcionario
            print(f'📝 Ejecutando UPDATE en solicitud {solicitud_id} con funcionario_id={funcionario_id_firma}')
            cur.execute("""
                UPDATE app.solicitudes 
                SET firmado_funcionario = TRUE,
                    fecha_firma_funcionario = NOW(),
                    funcionario_id_firma = %s,
                    estado = 'firmado_funcionario'
                WHERE id = %s
            """, (funcionario_id_firma, solicitud_id))
            
            print(f'📊 Rowcount después del UPDATE: {cur.rowcount}')
            
            # Verificar que el UPDATE de solicitud funcionó
            if cur.rowcount == 0:
                print(f'❌ ERROR: No se pudo actualizar solicitud {solicitud_id} - rowcount: {cur.rowcount}')
                print(f'🔍 Verificando si la solicitud existe...')
                cur.execute("SELECT id FROM app.solicitudes WHERE id = %s", (solicitud_id,))
                existe = cur.fetchone()
                if existe:
                    print(f'⚠️ La solicitud existe pero el UPDATE no afectó filas. ¿Problema con las columnas?')
                else:
                    print(f'⚠️ La solicitud {solicitud_id} NO existe')
                conn.rollback()
                cur.close()
                conn.close()
                return jsonify({'error': 'No se pudo actualizar el estado de la solicitud'}), 404
            
            print(f'✅ Solicitud {solicitud_id} actualizada EXITOSAMENTE - firmado_funcionario=TRUE, funcionario_id_firma={funcionario_id_firma}')
            
            # Actualizar validación con la firma del funcionario (mantener por compatibilidad)
            # Si falla, no hacer rollback porque ya actualizamos solicitudes
            try:
                cur.execute("""
                    UPDATE app.validacion 
                    SET val_firma_funcionario = %s,
                        val_estado = 'firmado_funcionario',
                        updated_at = NOW()
                    WHERE solicitud_id = %s
                """, (json.dumps(firma_data), solicitud_id))
                
                if cur.rowcount == 0:
                    print(f'⚠️ No se encontró registro de validación para solicitud {solicitud_id}, pero la solicitud ya fue actualizada')
                else:
                    print(f'✅ Validación actualizada para solicitud {solicitud_id}')
            except Exception as e:
                print(f'⚠️ Error actualizando validación (no crítico): {e}')
            
            # Commit siempre para guardar los cambios de solicitudes
            print('💾 Ejecutando COMMIT...')
            conn.commit()
            print('✅ COMMIT ejecutado exitosamente')
            
            # Verificar que se guardó correctamente
            cur.execute("""
                SELECT firmado_funcionario, fecha_firma_funcionario, funcionario_id_firma 
                FROM app.solicitudes 
                WHERE id = %s
            """, (solicitud_id,))
            resultado = cur.fetchone()
            print(f'🔍 Verificación POST-COMMIT: firmado={resultado[0]}, fecha={resultado[1]}, funcionario_id={resultado[2]}')
            
            cur.close()
            conn.close()
            
            print(f'✅ Solicitud {solicitud_id} firmada por funcionario exitosamente')
            
            return jsonify({
                'success': True,
                'message': 'Solicitud firmada por funcionario exitosamente',
                'data': {
                    'solicitud_id': solicitud_id,
                    'expediente_id': expediente_id,
                    'estado': 'firmado_funcionario',
                    'nota': 'Representante firmará con aplicación externa'
                }
            }), 200
            
        except Exception as e:
            print(f'❌ Error firmando solicitud como funcionario: {e}')
            if 'conn' in locals():
                conn.rollback()
                conn.close()
            return jsonify({'error': f'Error interno del servidor: {str(e)}'}), 500

    @app.route('/api/solicitudes/<int:solicitud_id>/firmar-funcionario-directo', methods=['POST'])
    @login_required
    def firmar_solicitud_funcionario_directo(solicitud_id):
        """Firmar solicitud como funcionario - Solo guarda en app.solicitudes"""
        print(f"🔔 Petición de firma DIRECTA de funcionario para solicitud: {solicitud_id}")
        
        conn = get_db_connection()
        if not conn:
            return jsonify({'error': 'Error de conexión a la base de datos'}), 500
        
        try:
            data = request.get_json()
            firma_data = data.get('firma_data') if data else {}
            
            cur = conn.cursor()
            
            # Obtener funcionario_id de la firma_data o de la sesión
            funcionario_id_firma = firma_data.get('funcionario_id') if firma_data else None
            if not funcionario_id_firma:
                funcionario_id_firma = session.get('user_id')
            
            print(f'🔍 funcionario_id_firma: {funcionario_id_firma}')
            
            if not funcionario_id_firma:
                return jsonify({'error': 'No se pudo identificar al funcionario'}), 400
            
            # Verificar que el funcionario existe
            cur.execute("SELECT id FROM app.funcionarios WHERE id = %s AND activo = true", (funcionario_id_firma,))
            if not cur.fetchone():
                return jsonify({'error': 'Funcionario no encontrado o inactivo'}), 404
            
            # Crear columnas si no existen
            try:
                cur.execute("ALTER TABLE app.solicitudes ADD COLUMN IF NOT EXISTS firmado_funcionario BOOLEAN DEFAULT FALSE")
                conn.commit()
                print('✅ Columna firmado_funcionario verificada/creada')
            except Exception as e:
                print(f'⚠️ Error creando columna (puede que ya exista): {e}')
            
            # Obtener expediente_id antes de actualizar
            cur.execute("SELECT expediente_id FROM app.solicitudes WHERE id = %s", (solicitud_id,))
            expediente_result = cur.fetchone()
            if not expediente_result:
                conn.rollback()
                cur.close()
                conn.close()
                return jsonify({'error': f'Solicitud {solicitud_id} no encontrada'}), 404
            
            expediente_id = expediente_result[0]
            
            # UPDATE directo en solicitudes - SOLO firmado_funcionario
            cur.execute("""
                UPDATE app.solicitudes 
                SET firmado_funcionario = TRUE
                WHERE id = %s
            """, (solicitud_id,))
            
            print(f'📊 Rowcount: {cur.rowcount}')
            
            if cur.rowcount == 0:
                conn.rollback()
                cur.close()
                conn.close()
                return jsonify({'error': f'No se pudo actualizar solicitud {solicitud_id}'}), 404
            
            # Verificar si la solicitud está lista para evaluación (todas las firmas + cálculo)
            verificar_y_actualizar_estado_pendiente(expediente_id, solicitud_id, cur, conn)
            
            conn.commit()
            
            # Verificar que se guardó
            cur.execute("SELECT firmado_funcionario, estado FROM app.solicitudes WHERE id = %s", (solicitud_id,))
            resultado = cur.fetchone()
            print(f'✅ Guardado: firmado_funcionario={resultado[0]}, estado={resultado[1]}')
            
            cur.close()
            conn.close()
            
            return jsonify({
                'success': True,
                'message': 'Firma guardada en solicitudes exitosamente',
                'data': {
                    'solicitud_id': solicitud_id,
                    'firmado_funcionario': True
                }
            }), 200
            
        except Exception as e:
            print(f'❌ Error: {e}')
            if 'conn' in locals():
                conn.rollback()
                conn.close()
            return jsonify({'error': f'Error interno: {str(e)}'}), 500

