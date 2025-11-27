"""
Rutas de gestión de expedientes
"""
from flask import request, jsonify
from psycopg2.extras import RealDictCursor
from datetime import datetime
from utils.database import get_db_connection
from middleware.auth import login_required

def register_routes(app):
    """Registrar rutas de expedientes"""
    
    @app.route('/api/expediente/<int:expediente_id>', methods=['GET'])
    def obtener_expediente(expediente_id):
        """Obtener un expediente completo con todos sus datos - Optimizado con JOINs (de 7 queries a 3)"""
        conn = get_db_connection()
        if not conn:
            return jsonify({'error': 'Error de conexión a la base de datos'}), 500
        
        try:
            cur = conn.cursor(cursor_factory=RealDictCursor)
            
            # Query 1: Expediente + Representante + Causante (relaciones 1:1, optimizado con JOINs)
            cur.execute("""
                SELECT 
                    e.id, e.expediente_numero, e.estado, e.observaciones, 
                    e.fecha_creacion, e.funcionario_id,
                    r.id as rep_id, r.rep_nombre, r.rep_apellido_p, r.rep_apellido_m, 
                    r.rep_rut, r.rep_calidad, r.rep_telefono, r.rep_email, r.rep_direccion,
                    c.id as caus_id, c.fal_nombre, c.fal_apellido_p, c.fal_apellido_m,
                    c.fal_run, c.fal_fecha_defuncion, c.fal_comuna_defuncion, c.fal_nacionalidad
                FROM app.expediente e
                LEFT JOIN app.representante r ON e.id = r.expediente_id
                LEFT JOIN app.causante c ON e.id = c.expediente_id
                WHERE e.id = %s
            """, (expediente_id,))
            
            result = cur.fetchone()
            
            if not result:
                cur.close()
                conn.close()
                return jsonify({'error': 'Expediente no encontrado'}), 404
            
            # Construir objetos expediente, representante y causante
            expediente = {
                'id': result['id'],
                'expediente_numero': result['expediente_numero'],
                'estado': result['estado'],
                'observaciones': result['observaciones'],
                'fecha_creacion': result['fecha_creacion'],
                'funcionario_id': result['funcionario_id']
            }
            
            representante = None
            if result.get('rep_id'):
                representante = {
                    'id': result['rep_id'],
                    'rep_nombre': result.get('rep_nombre'),
                    'rep_apellido_p': result.get('rep_apellido_p'),
                    'rep_apellido_m': result.get('rep_apellido_m'),
                    'rep_rut': result.get('rep_rut'),
                    'rep_calidad': result.get('rep_calidad'),
                    'rep_telefono': result.get('rep_telefono'),
                    'rep_email': result.get('rep_email'),
                    'rep_direccion': result.get('rep_direccion'),
                    'expediente_id': expediente_id
                }
            
            causante = None
            if result.get('caus_id'):
                causante = {
                    'id': result['caus_id'],
                    'fal_nombre': result.get('fal_nombre'),
                    'fal_apellido_p': result.get('fal_apellido_p'),
                    'fal_apellido_m': result.get('fal_apellido_m'),
                    'fal_run': result.get('fal_run'),
                    'fal_fecha_defuncion': result.get('fal_fecha_defuncion'),
                    'fal_comuna_defuncion': result.get('fal_comuna_defuncion'),
                    'fal_nacionalidad': result.get('fal_nacionalidad'),
                    'expediente_id': expediente_id
                }
            
            # Query 2: Solicitudes, Beneficiarios y Documentos (relaciones 1:many, optimizado con subconsultas)
            cur.execute("""
                SELECT 
                    (SELECT json_agg(row_to_json(s)) FROM (
                        SELECT * FROM app.solicitudes WHERE expediente_id = %s
                    ) s) as solicitudes,
                    (SELECT json_agg(row_to_json(b)) FROM (
                        SELECT * FROM app.beneficiarios WHERE expediente_id = %s
                    ) b) as beneficiarios,
                    (SELECT json_agg(row_to_json(d)) FROM (
                        SELECT * FROM app.documentos_saldo_insoluto WHERE expediente_id = %s
                    ) d) as documentos
            """, (expediente_id, expediente_id, expediente_id))
            
            result2 = cur.fetchone()
            
            solicitudes = result2['solicitudes'] if result2['solicitudes'] else []
            beneficiarios = result2['beneficiarios'] if result2['beneficiarios'] else []
            documentos = result2['documentos'] if result2['documentos'] else []
            
            # Query 3: Validación (relación 1:1)
            cur.execute("SELECT * FROM app.validacion WHERE expediente_id = %s", (expediente_id,))
            validacion_result = cur.fetchone()
            validacion = dict(validacion_result) if validacion_result else None
            
            response = {
                'expediente': expediente,
                'representante': representante,
                'causante': causante,
                'solicitudes': solicitudes,
                'beneficiarios': beneficiarios,
                'documentos': documentos,
                'validacion': validacion
            }
            
            cur.close()
            conn.close()
            return jsonify(response), 200
            
        except Exception as e:
            if 'cur' in locals():
                cur.close()
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
            
            # Query optimizada: Obtener beneficiarios, documentos y verificar firma del representante en una sola query
            cur.execute("""
                SELECT 
                    (SELECT json_agg(row_to_json(b)) FROM (
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
                    ) b) as beneficiarios,
                    (SELECT json_agg(row_to_json(d)) FROM (
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
                    ) d) as documentos,
                    EXISTS(
                        SELECT 1 FROM app.usuarios_firma 
                        WHERE UPPER(rut) = UPPER(%s)
                    ) as representante_firmado
            """, (expediente['expediente_id'], expediente['expediente_id'], expediente.get('rep_rut', '')))
            
            result_extra = cur.fetchone()
            
            beneficiarios = result_extra['beneficiarios'] if result_extra['beneficiarios'] else []
            documentos = result_extra['documentos'] if result_extra['documentos'] else []
            representante_firmado = result_extra['representante_firmado'] if expediente.get('rep_rut') else False
            
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
                
                # Manejar fecha_subida: puede venir como string (desde JSON) o datetime
                fecha_subida = 'No especificada'
                if doc['doc_fecha_subida']:
                    if isinstance(doc['doc_fecha_subida'], str):
                        # Si es string, parsearlo y formatearlo
                        try:
                            fecha_obj = datetime.fromisoformat(doc['doc_fecha_subida'].replace('Z', '+00:00'))
                            fecha_subida = fecha_obj.strftime('%d/%m/%Y %H:%M')
                        except (ValueError, AttributeError):
                            # Si falla el parsing, usar el string original
                            fecha_subida = doc['doc_fecha_subida']
                    elif hasattr(doc['doc_fecha_subida'], 'strftime'):
                        # Si es datetime, usar strftime directamente
                        fecha_subida = doc['doc_fecha_subida'].strftime('%d/%m/%Y %H:%M')
                    else:
                        fecha_subida = str(doc['doc_fecha_subida'])
                
                documento = {
                    'id': doc['id'],
                    'nombre': doc['doc_nombre_archivo'],
                    'tipo_id': doc['doc_tipo_id'],
                    'tamano_mb': round(tamano_mb, 2),
                    'mime_type': doc['doc_mime_type'],
                    'fecha_subida': fecha_subida,
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
