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

    @app.route('/api/revision-expediente', methods=['POST'])
    @login_required
    def revision_expediente():
        """Obtener expediente completo por RUT del causante para revisión"""
        print("🔔 Petición de revisión de expediente")
        
        conn = get_db_connection()
        if not conn:
            return jsonify({'error': 'Error de conexión a la base de datos'}), 500
        
        try:
            data = request.get_json()
            
            # Validar datos requeridos
            if not data.get('rut'):
                return jsonify({'error': 'RUT es requerido'}), 400
            
            rut = data['rut'].strip()
            
            # Validar formato básico de RUT
            rut_limpio = rut.replace('.', '').replace('-', '').upper()
            if len(rut_limpio) < 8 or len(rut_limpio) > 9:
                return jsonify({'error': 'Formato de RUT inválido'}), 400
            
            if not rut_limpio[:-1].isdigit() or rut_limpio[-1] not in '0123456789K':
                return jsonify({'error': 'Formato de RUT inválido'}), 400
            
            cur = conn.cursor(cursor_factory=RealDictCursor)
            
            # Obtener expediente completo por RUT del causante
            cur.execute("""
                SELECT DISTINCT
                    e.id as expediente_id,
                    e.expediente_numero,
                    e.estado as estado_expediente,
                    e.observaciones,
                    e.fecha_creacion,
                    e.funcionario_id,
                    f.iniciales as funcionario_iniciales,
                    f.nombres as funcionario_nombres,
                    f.apellido_p as funcionario_apellido_p,
                    f.apellido_m as funcionario_apellido_m,
                    c.fal_nombre,
                    c.fal_apellido_p,
                    c.fal_apellido_m,
                    c.fal_run,
                    c.fal_fecha_defuncion,
                    c.fal_comuna_defuncion,
                    c.fal_nacionalidad,
                    s.id as solicitud_id,
                    s.folio,
                    s.estado as estado_solicitud,
                    s.firmado_funcionario,
                    s.sucursal,
                    s.observacion as motivo_solicitud,
                    r.rep_nombre,
                    r.rep_apellido_p,
                    r.rep_apellido_m,
                    r.rep_rut,
                    r.rep_calidad,
                    r.rep_telefono,
                    r.rep_email,
                    COUNT(DISTINCT b.id) as total_beneficiarios,
                    COUNT(DISTINCT uf.id) as beneficiarios_firmados,
                    COUNT(DISTINCT d.id) as total_documentos
                FROM app.expediente e
                JOIN app.causante c ON e.id = c.expediente_id
                JOIN app.solicitudes s ON e.id = s.expediente_id
                LEFT JOIN app.funcionarios f ON e.funcionario_id = f.id
                LEFT JOIN app.representante r ON e.id = r.expediente_id
                LEFT JOIN app.beneficiarios b ON e.id = b.expediente_id
                LEFT JOIN app.usuarios_firma uf ON b.ben_run = uf.rut
                LEFT JOIN app.documentos_saldo_insoluto d ON e.id = d.expediente_id
                WHERE c.fal_run = %s
                GROUP BY e.id, e.expediente_numero, e.estado, e.observaciones, e.fecha_creacion, e.funcionario_id,
                         f.iniciales, f.nombres, f.apellido_p, f.apellido_m,
                         c.fal_nombre, c.fal_apellido_p, c.fal_apellido_m, c.fal_run,
                         c.fal_fecha_defuncion, c.fal_comuna_defuncion, c.fal_nacionalidad,
                         s.id, s.folio, s.estado, s.firmado_funcionario, s.sucursal, s.observacion,
                         r.rep_nombre, r.rep_apellido_p, r.rep_apellido_m, r.rep_rut,
                         r.rep_calidad, r.rep_telefono, r.rep_email
                ORDER BY e.fecha_creacion DESC
                LIMIT 1
            """, (rut,))
            
            expediente = cur.fetchone()
            
            if not expediente:
                cur.close()
                conn.close()
                return jsonify({
                    'success': True,
                    'message': 'No se encontró expediente para el RUT proporcionado',
                    'data': {
                        'rut': rut,
                        'expediente_id': None
                    }
                }), 200
            
            # Obtener beneficiarios del expediente
            cur.execute("""
                SELECT 
                    b.id,
                    b.expediente_id,
                    b.ben_nombre,
                    b.ben_run,
                    b.ben_parentesco,
                    uf.id as firma_id,
                    uf.rut as firma_rut
                FROM app.beneficiarios b
                LEFT JOIN app.usuarios_firma uf ON b.ben_run = uf.rut
                WHERE b.expediente_id = %s
                ORDER BY b.id
            """, (expediente['expediente_id'],))
            
            beneficiarios = cur.fetchall()
            
            # Obtener documentos del expediente
            cur.execute("""
                SELECT 
                    d.id,
                    d.doc_nombre_archivo,
                    d.doc_tipo_id,
                    d.doc_tamano_bytes,
                    d.doc_mime_type,
                    d.doc_fecha_subida,
                    d.doc_estado,
                    d.doc_ruta_storage
                FROM app.documentos_saldo_insoluto d
                WHERE d.expediente_id = %s
                ORDER BY d.doc_fecha_subida DESC
            """, (expediente['expediente_id'],))
            
            documentos = cur.fetchall()
            
            # Determinar estado de firma del representante ANTES de cerrar el cursor
            representante_firmado = False
            
            if expediente['rep_rut']:
                # Verificar si el RUT del representante está en usuarios_firma (ignorando mayúsculas/minúsculas)
                cur.execute("""
                    SELECT id FROM app.usuarios_firma 
                    WHERE UPPER(rut) = UPPER(%s)
                """, (expediente['rep_rut'],))
                
                if cur.fetchone():
                    representante_firmado = True
                else:
                    representante_firmado = False
            
            cur.close()
            conn.close()
            
            # Procesar datos del expediente
            pendientes_firmas_beneficiarios = expediente['total_beneficiarios'] - expediente['beneficiarios_firmados']
            
            # Calcular total de firmas (beneficiarios + representante)
            total_firmas = expediente['total_beneficiarios'] + 1  # +1 por el representante
            firmas_completadas = expediente['beneficiarios_firmados'] + (1 if representante_firmado else 0)
            pendientes_firmas = total_firmas - firmas_completadas
            
            # Determinar estado de firmas
            if total_firmas == 1:  # Solo representante, sin beneficiarios
                estado_firmas = 'Solo representante'
                color_firmas = '#6c757d'
                icono_firmas = '👨‍💼'
            elif pendientes_firmas == 0:
                estado_firmas = 'Firmas completas'
                color_firmas = '#28a745'
                icono_firmas = '✅'
            else:
                estado_firmas = f'Pendientes: {pendientes_firmas}'
                color_firmas = '#ffc107'
                icono_firmas = '⚠️'
            
            # Procesar beneficiarios
            beneficiarios_procesados = []
            for ben in beneficiarios:
                beneficiario = {
                    'id': ben['id'],
                    'expediente_id': ben['expediente_id'],
                    'nombre_completo': ben['ben_nombre'] or 'Sin nombre',
                    'rut': ben['ben_run'],
                    'parentesco': ben['ben_parentesco'],
                    'firma': {
                        'firmado': ben['firma_id'] is not None,
                        'rut_firma': ben['firma_rut'] if ben['firma_rut'] else None
                    }
                }
                beneficiarios_procesados.append(beneficiario)
            
            # Procesar documentos
            documentos_procesados = []
            for doc in documentos:
                tamano_mb = (doc['doc_tamano_bytes'] / (1024 * 1024)) if doc['doc_tamano_bytes'] else 0
                
                documento = {
                    'id': doc['id'],
                    'nombre': doc['doc_nombre_archivo'],
                    'tipo_id': doc['doc_tipo_id'],
                    'tamano_mb': round(tamano_mb, 2),
                    'mime_type': doc['doc_mime_type'],
                    'fecha_subida': doc['doc_fecha_subida'].strftime('%d/%m/%Y %H:%M') if doc['doc_fecha_subida'] else 'No especificada',
                    'estado': doc['doc_estado'],
                    'ruta_descarga': doc['doc_ruta_storage']
                }
                documentos_procesados.append(documento)
            
            resultado = {
                'expediente_id': expediente['expediente_id'],
                'expediente_numero': expediente['expediente_numero'],
                'folio': expediente['folio'],
                'estado_expediente': expediente['estado_expediente'],
                'fecha_creacion': expediente['fecha_creacion'].strftime('%d/%m/%Y %H:%M') if expediente['fecha_creacion'] else 'No especificada',
                'causante': {
                    'nombre_completo': f"{expediente['fal_nombre']} {expediente['fal_apellido_p']} {expediente['fal_apellido_m'] or ''}".strip(),
                    'rut': expediente['fal_run'],
                    'fecha_defuncion': expediente['fal_fecha_defuncion'].strftime('%Y-%m-%d') if expediente['fal_fecha_defuncion'] else None,
                    'comuna_defuncion': expediente['fal_comuna_defuncion'] or 'No especificada',
                    'nacionalidad': expediente['fal_nacionalidad'] or 'No especificada'
                },
                'representante': {
                    'nombre_completo': f"{expediente['rep_nombre'] or ''} {expediente['rep_apellido_p'] or ''} {expediente['rep_apellido_m'] or ''}".strip() if expediente['rep_nombre'] else 'No especificado',
                    'rut': expediente['rep_rut'] or 'No especificado',
                    'calidad': expediente['rep_calidad'] or 'No especificada',
                    'telefono': expediente['rep_telefono'] or 'No especificado',
                    'email': expediente['rep_email'] or 'No especificado',
                    'firmado': representante_firmado
                },
                'solicitud': {
                    'id': expediente['solicitud_id'],
                    'sucursal': expediente['sucursal'] or 'No especificada',
                    'motivo': expediente['motivo_solicitud'] or 'No especificado',
                    'estado': expediente['estado_solicitud'],
                    'firmado_funcionario': expediente.get('firmado_funcionario', False)
                },
                'funcionario': {
                    'id': expediente['funcionario_id'] or 'No especificado',
                    'iniciales': expediente['funcionario_iniciales'] or 'No especificado',
                    'nombre_completo': f"{expediente['funcionario_nombres'] or ''} {expediente['funcionario_apellido_p'] or ''} {expediente['funcionario_apellido_m'] or ''}".strip() if expediente['funcionario_nombres'] else 'No especificado'
                },
                'firmas': {
                    'total_firmas': total_firmas,
                    'firmas_completadas': firmas_completadas,
                    'pendientes': pendientes_firmas,
                    'estado': estado_firmas,
                    'color': color_firmas,
                    'icono': icono_firmas,
                    'detalle': {
                        'beneficiarios': {
                            'total': expediente['total_beneficiarios'],
                            'firmados': expediente['beneficiarios_firmados'],
                            'pendientes': pendientes_firmas_beneficiarios
                        },
                        'representante': {
                            'firmado': representante_firmado
                        }
                    }
                },
                'documentos': {
                    'total': expediente['total_documentos'],
                    'lista': documentos_procesados
                },
                'beneficiarios': beneficiarios_procesados
            }
            
            print(f'✅ Revisión exitosa para RUT {rut}: Expediente {expediente["expediente_numero"]}')
            
            return jsonify({
                'success': True,
                'message': f'Expediente encontrado: {expediente["expediente_numero"]}',
                'data': resultado
            }), 200
            
        except Exception as e:
            print(f'❌ Error en revisión de expediente: {e}')
            import traceback
            print(traceback.format_exc())
            if 'conn' in locals():
                conn.close()
            return jsonify({'error': f'Error interno del servidor: {str(e)}'}), 500
