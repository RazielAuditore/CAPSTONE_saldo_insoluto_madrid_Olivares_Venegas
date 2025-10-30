"""
Rutas de gestión de expedientes
"""
from flask import request, jsonify
from psycopg2.extras import RealDictCursor
from utils.database import get_db_connection
from routes.auth import login_required

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

    @app.route('/api/buscar-saldo-insoluto', methods=['POST'])
    @login_required
    def buscar_saldo_insoluto():
        """Buscar saldos insolutos por RUT del causante"""
        conn = get_db_connection()
        if not conn:
            return jsonify({'error': 'Error de conexión a la base de datos'}), 500
        
        try:
            data = request.get_json()
            
            if not data.get('rut'):
                return jsonify({'error': 'RUT es requerido'}), 400
            
            rut = data['rut'].strip()
            rut_limpio = rut.replace('.', '').replace('-', '').upper()
            
            if len(rut_limpio) < 8 or len(rut_limpio) > 9:
                return jsonify({'error': 'Formato de RUT inválido'}), 400
            
            if not rut_limpio[:-1].isdigit() or rut_limpio[-1] not in '0123456789K':
                return jsonify({'error': 'Formato de RUT inválido'}), 400
            
            cur = conn.cursor(cursor_factory=RealDictCursor)
            
            cur.execute("""
                SELECT DISTINCT
                    e.id as expediente_id, e.expediente_numero, e.estado as estado_expediente,
                    e.observaciones, c.fal_nombre, c.fal_apellido_p, c.fal_apellido_m, c.fal_run,
                    c.fal_fecha_defuncion, c.fal_comuna_defuncion, s.folio, s.estado as estado_solicitud,
                    s.sucursal, e.fecha_creacion, COUNT(b.id) as total_beneficiarios,
                    COUNT(uf.id) as beneficiarios_firmados
                FROM app.expediente e
                JOIN app.causante c ON e.id = c.expediente_id
                JOIN app.solicitudes s ON e.id = s.expediente_id
                LEFT JOIN app.beneficiarios b ON e.id = b.expediente_id
                LEFT JOIN app.usuarios_firma uf ON b.ben_run = uf.rut
                WHERE c.fal_run = %s
                GROUP BY e.id, e.expediente_numero, e.estado, e.observaciones, e.fecha_creacion,
                         c.fal_nombre, c.fal_apellido_p, c.fal_apellido_m, c.fal_run,
                         c.fal_fecha_defuncion, c.fal_comuna_defuncion, s.folio, s.estado, s.sucursal
                ORDER BY e.fecha_creacion DESC
            """, (rut,))
            
            expedientes = cur.fetchall()
            
            if not expedientes:
                cur.close()
                conn.close()
                return jsonify({
                    'success': True,
                    'message': 'No se encontraron saldos insolutos',
                    'data': {'rut': rut, 'expedientes': [], 'total': 0}
                }), 200
            
            resultados = []
            for exp in expedientes:
                pendientes_firmas = exp['total_beneficiarios'] - exp['beneficiarios_firmados']
                
                if exp['estado_solicitud'] == 'completado':
                    estado_general = 'Completado'
                    color_estado = '#28a745'
                elif pendientes_firmas == 0 and exp['total_beneficiarios'] > 0:
                    estado_general = 'Firmas Completas'
                    color_estado = '#17a2b8'
                elif pendientes_firmas > 0:
                    estado_general = f'Pendiente ({pendientes_firmas} firmas)'
                    color_estado = '#ffc107'
                else:
                    estado_general = 'En Proceso'
                    color_estado = '#6c757d'
                
                resultados.append({
                    'expediente_id': exp['expediente_id'],
                    'expediente_numero': exp['expediente_numero'],
                    'folio': exp['folio'],
                    'causante': {
                        'nombre_completo': f"{exp['fal_nombre']} {exp['fal_apellido_p']} {exp['fal_apellido_m'] or ''}".strip(),
                        'rut': exp['fal_run'],
                        'fecha_defuncion': exp['fal_fecha_defuncion'].strftime('%d/%m/%Y') if exp['fal_fecha_defuncion'] else 'No especificada'
                    },
                    'firmas': {
                        'total_beneficiarios': exp['total_beneficiarios'],
                        'beneficiarios_firmados': exp['beneficiarios_firmados'],
                        'pendientes': pendientes_firmas
                    },
                    'estado_general': estado_general,
                    'color_estado': color_estado
                })
            
            cur.close()
            conn.close()
            
            return jsonify({
                'success': True,
                'message': f'Se encontraron {len(resultados)} saldo(s) insoluto(s)',
                'data': {'rut': rut, 'expedientes': resultados, 'total': len(resultados)}
            }), 200
            
        except Exception as e:
            if 'conn' in locals():
                conn.close()
            return jsonify({'error': f'Error interno del servidor: {str(e)}'}), 500


