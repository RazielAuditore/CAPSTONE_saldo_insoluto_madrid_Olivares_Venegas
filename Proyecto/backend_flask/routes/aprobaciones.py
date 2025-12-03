"""
Rutas de gestión de aprobaciones y rechazos
"""
from flask import request, jsonify, session
from psycopg2.extras import RealDictCursor
from utils.database import get_db_connection
from middleware.auth import login_required

def register_routes(app):
    """Registrar rutas de aprobaciones"""
    
    @app.route('/api/solicitudes-pendientes', methods=['GET'])
    @login_required
    def solicitudes_pendientes():
        """Obtener solicitudes pendientes de aprobación por jefatura"""
        print("🔔 Petición de solicitudes pendientes")
        
        conn = get_db_connection()
        if not conn:
            return jsonify({'error': 'Error de conexión a la base de datos'}), 500
        
        try:
            estado_filtro = request.args.get('estado', '')
            sucursal_filtro = request.args.get('sucursal', '')
            
            cur = conn.cursor(cursor_factory=RealDictCursor)
            
            # Construir consulta base
            query = """
                SELECT DISTINCT
                    e.id as expediente_id,
                    e.expediente_numero,
                    e.fecha_creacion,
                    s.id as solicitud_id,
                    s.folio,
                    s.estado as estado_solicitud,
                    s.firmado_funcionario,
                    s.sucursal,
                    c.fal_nombre || ' ' || c.fal_apellido_p || ' ' || COALESCE(c.fal_apellido_m, '') as causante_nombre_completo,
                    c.fal_run as causante_rut,
                    c.fal_fecha_defuncion as causante_fecha_defuncion,
                    r.rep_nombre || ' ' || COALESCE(r.rep_apellido_p, '') || ' ' || COALESCE(r.rep_apellido_m, '') as representante_nombre_completo,
                    r.rep_rut as representante_rut,
                    r.rep_calidad as representante_calidad,
                    COUNT(DISTINCT b.id) as total_beneficiarios,
                    COUNT(DISTINCT uf.id) as beneficiarios_firmados,
                    COUNT(DISTINCT d.id) as total_documentos
                FROM app.expediente e
                JOIN app.solicitudes s ON e.id = s.expediente_id
                JOIN app.causante c ON e.id = c.expediente_id
                LEFT JOIN app.representante r ON e.id = r.expediente_id
                LEFT JOIN app.beneficiarios b ON e.id = b.expediente_id
                LEFT JOIN app.usuarios_firma uf ON b.ben_run = uf.rut
                LEFT JOIN app.documentos_saldo_insoluto d ON e.id = d.expediente_id
                WHERE 1=1
            """
            
            params = []
            
            # Filtro por estado
            if estado_filtro:
                # Filtrar por estado exacto (pendiente o completado)
                query += " AND s.estado = %s"
                params.append(estado_filtro)
            else:
                # Por defecto, mostrar solo pendientes (en revisión)
                query += " AND s.estado = 'pendiente'"
            
            # Filtro por sucursal
            if sucursal_filtro:
                query += " AND s.sucursal = %s"
                params.append(sucursal_filtro)
            
            query += """
                GROUP BY e.id, e.expediente_numero, e.fecha_creacion,
                         s.id, s.folio, s.estado, s.firmado_funcionario, s.sucursal,
                         c.fal_nombre, c.fal_apellido_p, c.fal_apellido_m, c.fal_run, c.fal_fecha_defuncion,
                         r.rep_nombre, r.rep_apellido_p, r.rep_apellido_m, r.rep_rut, r.rep_calidad
                ORDER BY e.fecha_creacion DESC
            """
            
            cur.execute(query, tuple(params))
            solicitudes = cur.fetchall()
            
            # Procesar resultado
            resultados = []
            for s in solicitudes:
                pendientes_firmas = (s['total_beneficiarios'] or 0) - (s['beneficiarios_firmados'] or 0)
                
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
                """, (s['expediente_id'],))
                
                documentos_db = cur.fetchall()
                documentos_lista = []
                for doc in documentos_db:
                    tamano_mb = (doc['doc_tamano_bytes'] / (1024 * 1024)) if doc['doc_tamano_bytes'] else 0
                    documentos_lista.append({
                        'id': doc['id'],
                        'nombre': doc['doc_nombre_archivo'],
                        'tipo_id': doc['doc_tipo_id'],
                        'tamano_mb': round(tamano_mb, 2),
                        'mime_type': doc['doc_mime_type'],
                        'fecha_subida': doc['doc_fecha_subida'].strftime('%d/%m/%Y %H:%M') if doc['doc_fecha_subida'] else 'No especificada',
                        'estado': doc['doc_estado'],
                        'ruta_descarga': doc['doc_ruta_storage']
                    })
                
                # Verificar si representante tiene firma
                representante_firmado = False
                if s['representante_rut']:
                    cur.execute("""
                        SELECT id FROM app.usuarios_firma 
                        WHERE UPPER(rut) = UPPER(%s)
                    """, (s['representante_rut'],))
                    if cur.fetchone():
                        representante_firmado = True
                
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
                """, (s['expediente_id'],))
                
                beneficiarios_db = cur.fetchall()
                beneficiarios_lista = []
                for ben in beneficiarios_db:
                    beneficiarios_lista.append({
                        'id': ben['id'],
                        'expediente_id': ben['expediente_id'],
                        'nombre_completo': ben['ben_nombre'] or 'Sin nombre',
                        'rut': ben['ben_run'],
                        'parentesco': ben['ben_parentesco'],
                        'firma': {
                            'firmado': ben['firma_id'] is not None,
                            'rut_firma': ben['firma_rut'] if ben['firma_rut'] else None
                        }
                    })
                
                resultados.append({
                    'expediente_id': s['expediente_id'],
                    'solicitud_id': s['solicitud_id'],
                    'folio': s['folio'],
                    'estado_solicitud': s['estado_solicitud'],
                    'firmado_funcionario': s.get('firmado_funcionario', False),
                    'fecha_creacion': s['fecha_creacion'].isoformat() if s['fecha_creacion'] else None,
                    'sucursal': s['sucursal'],
                    'causante': {
                        'nombre_completo': s['causante_nombre_completo'],
                        'rut': s['causante_rut'],
                        'fecha_defuncion': s['causante_fecha_defuncion'].isoformat() if s['causante_fecha_defuncion'] else None
                    },
                    'representante': {
                        'nombre_completo': s['representante_nombre_completo'] or 'No especificado',
                        'rut': s['representante_rut'] or 'No especificado',
                        'calidad': s['representante_calidad'] or 'No especificada',
                        'firmado': representante_firmado
                    },
                    'firmas': {
                        'total_beneficiarios': s['total_beneficiarios'] or 0,
                        'beneficiarios_firmados': s['beneficiarios_firmados'] or 0,
                        'pendientes': max(0, pendientes_firmas)
                    },
                    'documentos': {
                        'total': s['total_documentos'] or 0,
                        'lista': documentos_lista
                    },
                    'beneficiarios': beneficiarios_lista
                })
            
            cur.close()
            conn.close()
            
            return jsonify({
                'success': True,
                'data': resultados
            }), 200
            
        except Exception as e:
            print(f'❌ Error obteniendo solicitudes pendientes: {e}')
            if 'conn' in locals():
                conn.close()
            return jsonify({'error': f'Error interno del servidor: {str(e)}'}), 500

    @app.route('/api/solicitudes/<int:solicitud_id>/aprobacion-items', methods=['GET'])
    @login_required
    def obtener_aprobacion_items(solicitud_id):
        """Obtener estado de aprobación de todos los items de una solicitud"""
        conn = get_db_connection()
        if not conn:
            return jsonify({'error': 'Error de conexión a la base de datos'}), 500
        
        try:
            cur = conn.cursor(cursor_factory=RealDictCursor)
            
            # Obtener expediente_id desde solicitud
            cur.execute("SELECT expediente_id FROM app.solicitudes WHERE id = %s", (solicitud_id,))
            solicitud = cur.fetchone()
            
            if not solicitud:
                cur.close()
                conn.close()
                return jsonify({'error': 'Solicitud no encontrada'}), 404
            
            expediente_id = solicitud['expediente_id']
            
            # Obtener todas las aprobaciones de items para esta solicitud
            cur.execute("""
                SELECT 
                    item_tipo,
                    estado,
                    observacion,
                    fecha_aprobacion,
                    f.nombres || ' ' || f.apellido_p as aprobado_por_nombre
                FROM app.aprobacion_items ai
                LEFT JOIN app.funcionarios f ON ai.aprobado_por = f.id
                WHERE ai.expediente_id = %s AND ai.solicitud_id = %s
                ORDER BY item_tipo
            """, (expediente_id, solicitud_id))
            
            items = cur.fetchall()
            
            # Convertir a diccionario por tipo de item
            items_dict = {}
            for item in items:
                items_dict[item['item_tipo']] = {
                    'estado': item['estado'],
                    'observacion': item['observacion'],
                    'fecha_aprobacion': item['fecha_aprobacion'].isoformat() if item['fecha_aprobacion'] else None,
                    'aprobado_por': item['aprobado_por_nombre']
                }
            
            cur.close()
            conn.close()
            
            return jsonify({
                'success': True,
                'data': items_dict
            }), 200
            
        except Exception as e:
            print(f'❌ Error obteniendo aprobación de items: {e}')
            if 'conn' in locals():
                conn.close()
            return jsonify({'error': f'Error interno del servidor: {str(e)}'}), 500

    @app.route('/api/solicitudes/<int:solicitud_id>/aprobacion-items', methods=['POST'])
    @login_required
    def aprobar_rechazar_item(solicitud_id):
        """Aprobar o rechazar un item específico de una solicitud"""
        conn = get_db_connection()
        if not conn:
            return jsonify({'error': 'Error de conexión a la base de datos'}), 500
        
        try:
            data = request.get_json()
            item_tipo = data.get('item_tipo')
            estado = data.get('estado')  # 'aprobado' o 'rechazado'
            observacion = data.get('observacion', '')
            
            # Validaciones
            if not item_tipo:
                return jsonify({'error': 'item_tipo es requerido'}), 400
            
            if estado not in ['aprobado', 'rechazado']:
                return jsonify({'error': 'estado debe ser "aprobado" o "rechazado"'}), 400
            
            if estado == 'rechazado' and not observacion:
                return jsonify({'error': 'La observación es obligatoria al rechazar un item'}), 400
            
            if item_tipo not in ['causante', 'beneficiarios', 'firmas', 'calculo', 'documentos', 'general']:
                return jsonify({'error': 'item_tipo inválido'}), 400
            
            cur = conn.cursor()
            funcionario_id = session.get('user_id')
            
            # Obtener expediente_id desde solicitud
            cur.execute("SELECT expediente_id FROM app.solicitudes WHERE id = %s", (solicitud_id,))
            solicitud = cur.fetchone()
            
            if not solicitud:
                cur.close()
                conn.close()
                return jsonify({'error': 'Solicitud no encontrada'}), 404
            
            expediente_id = solicitud[0]
            
            # Insertar o actualizar aprobación del item
            cur.execute("""
                INSERT INTO app.aprobacion_items 
                (expediente_id, solicitud_id, item_tipo, estado, observacion, aprobado_por, fecha_aprobacion)
                VALUES (%s, %s, %s, %s, %s, %s, NOW())
                ON CONFLICT (expediente_id, solicitud_id, item_tipo) 
                DO UPDATE SET 
                    estado = EXCLUDED.estado,
                    observacion = EXCLUDED.observacion,
                    aprobado_por = EXCLUDED.aprobado_por,
                    fecha_aprobacion = NOW(),
                    updated_at = NOW()
                RETURNING id
            """, (expediente_id, solicitud_id, item_tipo, estado, observacion if observacion else None, funcionario_id))
            
            aprobacion_id = cur.fetchone()[0]
            
            # Si se rechaza un item, cambiar estado de la solicitud a 'rechazado/enRevision'
            if estado == 'rechazado':
                # Verificar si hay otros items rechazados
                cur.execute("""
                    SELECT COUNT(*) FROM app.aprobacion_items 
                    WHERE expediente_id = %s AND solicitud_id = %s AND estado = 'rechazado'
                """, (expediente_id, solicitud_id))
                total_rechazados = cur.fetchone()[0]
                
                # Cambiar estado de solicitud a 'rechazado/enRevision' si hay al menos un item rechazado
                # Esto permite que el funcionario pueda editar y corregir
                # Si está en 'pendiente', cambiar a 'rechazado/enRevision'
                # Si ya está en 'rechazado/enRevision', mantenerlo
                cur.execute("""
                    UPDATE app.solicitudes 
                    SET estado = 'rechazado/enRevision'
                    WHERE id = %s AND estado = 'pendiente'
                """, (solicitud_id,))
            
            conn.commit()
            cur.close()
            conn.close()
            
            return jsonify({
                'success': True,
                'message': f'Item {item_tipo} {estado} exitosamente',
                'data': {
                    'id': aprobacion_id,
                    'item_tipo': item_tipo,
                    'estado': estado
                }
            }), 200
            
        except Exception as e:
            print(f'❌ Error aprobando/rechazando item: {e}')
            if 'conn' in locals():
                conn.rollback()
                conn.close()
            return jsonify({'error': f'Error interno del servidor: {str(e)}'}), 500

    @app.route('/api/solicitudes-rechazadas', methods=['GET'])
    @login_required
    def solicitudes_rechazadas():
        """Obtener solicitudes rechazadas del funcionario actual"""
        conn = get_db_connection()
        if not conn:
            return jsonify({'error': 'Error de conexión a la base de datos'}), 500
        
        try:
            funcionario_id = session.get('user_id')
            cur = conn.cursor(cursor_factory=RealDictCursor)
            
            # Obtener solicitudes rechazadas del funcionario (por expediente que gestionó)
            cur.execute("""
                SELECT DISTINCT
                    e.id as expediente_id,
                    e.expediente_numero,
                    e.fecha_creacion,
                    s.id as solicitud_id,
                    s.folio,
                    s.estado as estado_solicitud,
                    s.firmado_funcionario,
                    s.sucursal,
                    c.fal_nombre || ' ' || c.fal_apellido_p || ' ' || COALESCE(c.fal_apellido_m, '') as causante_nombre_completo,
                    c.fal_run as causante_rut,
                    COUNT(DISTINCT ai.id) FILTER (WHERE ai.estado = 'rechazado') as items_rechazados
                FROM app.expediente e
                JOIN app.solicitudes s ON e.id = s.expediente_id
                JOIN app.causante c ON e.id = c.expediente_id
                LEFT JOIN app.aprobacion_items ai ON s.id = ai.solicitud_id AND ai.estado = 'rechazado'
                WHERE s.estado = 'rechazado/enRevision' AND e.funcionario_id = %s
                GROUP BY e.id, e.expediente_numero, e.fecha_creacion,
                         s.id, s.folio, s.estado, s.firmado_funcionario, s.sucursal,
                         c.fal_nombre, c.fal_apellido_p, c.fal_apellido_m, c.fal_run
                ORDER BY e.fecha_creacion DESC
            """, (funcionario_id,))
            
            solicitudes = cur.fetchall()
            
            resultados = []
            for s in solicitudes:
                resultados.append({
                    'expediente_id': s['expediente_id'],
                    'solicitud_id': s['solicitud_id'],
                    'folio': s['folio'],
                    'estado_solicitud': s['estado_solicitud'],
                    'fecha_creacion': s['fecha_creacion'].isoformat() if s['fecha_creacion'] else None,
                    'sucursal': s['sucursal'],
                    'causante': {
                        'nombre_completo': s['causante_nombre_completo'],
                        'rut': s['causante_rut']
                    },
                    'items_rechazados': s['items_rechazados'] or 0
                })
            
            cur.close()
            conn.close()
            
            return jsonify({
                'success': True,
                'data': resultados
            }), 200
            
        except Exception as e:
            print(f'❌ Error obteniendo solicitudes rechazadas: {e}')
            if 'conn' in locals():
                conn.close()
            return jsonify({'error': f'Error interno del servidor: {str(e)}'}), 500

    @app.route('/api/solicitudes/<int:solicitud_id>/aprobar', methods=['POST'])
    @login_required
    def aprobar_solicitud_completa(solicitud_id):
        """Aprobar una solicitud completa - verifica que todos los items estén aprobados"""
        conn = get_db_connection()
        if not conn:
            return jsonify({'error': 'Error de conexión a la base de datos'}), 500
        
        try:
            cur = conn.cursor()
            funcionario_id = session.get('user_id')
            
            # Obtener expediente_id desde solicitud
            cur.execute("SELECT expediente_id, estado FROM app.solicitudes WHERE id = %s", (solicitud_id,))
            solicitud = cur.fetchone()
            
            if not solicitud:
                cur.close()
                conn.close()
                return jsonify({'error': 'Solicitud no encontrada'}), 404
            
            expediente_id = solicitud[0]
            estado_actual = solicitud[1]
            
            # Verificar que la solicitud no esté ya aprobada o rechazada
            if estado_actual == 'completado':
                cur.close()
                conn.close()
                return jsonify({'error': 'La solicitud ya está aprobada'}), 400
            
            # Permitir aprobar solicitudes en revisión (rechazado/enRevision)
            # Solo se pueden aprobar solicitudes en 'pendiente' o 'rechazado/enRevision'
            if estado_actual not in ['pendiente', 'rechazado/enRevision']:
                cur.close()
                conn.close()
                return jsonify({'error': f'No se puede aprobar una solicitud en estado: {estado_actual}. Debe estar en pendiente o rechazado/enRevision.'}), 400
            
            # Verificar que todos los items requeridos estén aprobados
            cur.execute("""
                SELECT item_tipo, estado 
                FROM app.aprobacion_items 
                WHERE expediente_id = %s AND solicitud_id = %s
            """, (expediente_id, solicitud_id))
            
            items = cur.fetchall()
            
            # Items requeridos que deben estar aprobados
            items_requeridos = ['causante', 'beneficiarios', 'firmas', 'calculo', 'documentos']
            items_aprobados = {item[0]: item[1] for item in items}
            
            # Verificar que todos los items requeridos estén aprobados
            items_faltantes = []
            for item_tipo in items_requeridos:
                if item_tipo not in items_aprobados or items_aprobados[item_tipo] != 'aprobado':
                    items_faltantes.append(item_tipo)
            
            if items_faltantes:
                cur.close()
                conn.close()
                return jsonify({
                    'error': f'Faltan items por aprobar: {", ".join(items_faltantes)}',
                    'items_faltantes': items_faltantes
                }), 400
            
            # Cambiar estado de la solicitud a 'completado'
            cur.execute("""
                UPDATE app.solicitudes 
                SET estado = 'completado'
                WHERE id = %s
            """, (solicitud_id,))
            
            # Actualizar estado del cálculo a 'aprobado' si existe
            cur.execute("""
                UPDATE app.calculo_saldo_insoluto 
                SET estado = 'aprobado',
                    updated_at = NOW()
                WHERE expediente_id = %s AND estado = 'pendiente'
            """, (expediente_id,))
            
            conn.commit()
            cur.close()
            conn.close()
            
            return jsonify({
                'success': True,
                'message': 'Solicitud aprobada exitosamente',
                'data': {
                    'solicitud_id': solicitud_id,
                    'estado': 'completado'
                }
            }), 200
            
        except Exception as e:
            print(f'❌ Error aprobando solicitud: {e}')
            if 'conn' in locals():
                conn.rollback()
                conn.close()
            return jsonify({'error': f'Error interno del servidor: {str(e)}'}), 500

    @app.route('/api/solicitudes/<int:solicitud_id>/reenviar', methods=['POST'])
    @login_required
    def reenviar_solicitud(solicitud_id):
        """Reenviar solicitud rechazada para nueva evaluación por jefatura"""
        print(f"🔄 Petición de reenvío para solicitud: {solicitud_id}")
        conn = get_db_connection()
        if not conn:
            return jsonify({'error': 'Error de conexión a la base de datos'}), 500
        
        try:
            cur = conn.cursor()
            
            # Verificar que la solicitud existe y está rechazada
            cur.execute("SELECT estado, expediente_id FROM app.solicitudes WHERE id = %s", (solicitud_id,))
            solicitud = cur.fetchone()
            
            if not solicitud:
                cur.close()
                conn.close()
                print(f"❌ Solicitud {solicitud_id} no encontrada")
                return jsonify({'error': 'Solicitud no encontrada'}), 404
            
            estado_actual = solicitud[0]
            expediente_id = solicitud[1]
            
            print(f"📊 Estado actual de solicitud {solicitud_id}: '{estado_actual}'")
            
            # Solo aceptar 'rechazado/enRevision' (estado cuando está siendo corregida)
            if estado_actual != 'rechazado/enRevision':
                cur.close()
                conn.close()
                print(f"⚠️ La solicitud no está en estado rechazado/enRevision. Estado: '{estado_actual}'")
                return jsonify({'error': f'La solicitud debe estar en estado rechazado/enRevision para reenviarla. Estado actual: {estado_actual}'}), 400
            
            # Cambiar estado de solicitud a 'pendiente'
            print(f"🔄 Cambiando estado de '{estado_actual}' a 'pendiente'...")
            cur.execute("""
                UPDATE app.solicitudes 
                SET estado = 'pendiente'
                WHERE id = %s
            """, (solicitud_id,))
            
            if cur.rowcount == 0:
                print(f"⚠️ No se pudo actualizar solicitud {solicitud_id} - rowcount: {cur.rowcount}")
            else:
                print(f"✅ Solicitud {solicitud_id} actualizada - rowcount: {cur.rowcount}")
            
            # Resetear items rechazados a 'pendiente' para nueva evaluación
            cur.execute("""
                UPDATE app.aprobacion_items 
                SET estado = 'pendiente',
                    observacion = NULL,
                    updated_at = NOW()
                WHERE expediente_id = %s AND solicitud_id = %s AND estado = 'rechazado'
            """, (expediente_id, solicitud_id))
            
            items_reseteados = cur.rowcount
            print(f"✅ Items rechazados reseteados: {items_reseteados}")
            
            # Mantener items aprobados como aprobados (no resetearlos)
            
            conn.commit()
            
            # Verificar que se guardó correctamente
            cur.execute("SELECT estado FROM app.solicitudes WHERE id = %s", (solicitud_id,))
            estado_verificado = cur.fetchone()[0]
            print(f"✅ Estado verificado después del commit: '{estado_verificado}'")
            
            cur.close()
            conn.close()
            
            return jsonify({
                'success': True,
                'message': 'Solicitud reenviada exitosamente para nueva evaluación',
                'data': {
                    'solicitud_id': solicitud_id,
                    'estado': 'pendiente',
                    'estado_anterior': estado_actual,
                    'items_reseteados': items_reseteados
                }
            }), 200
            
        except Exception as e:
            print(f'❌ Error reenviando solicitud: {e}')
            import traceback
            print(traceback.format_exc())
            if 'conn' in locals():
                conn.rollback()
                conn.close()
            return jsonify({'error': f'Error interno del servidor: {str(e)}'}), 500

    @app.route('/api/solicitudes/<int:solicitud_id>/enviar', methods=['POST'])
    @login_required
    def enviar_solicitud_revision(solicitud_id):
        """Enviar solicitud rechazada a revisión (cambia de 'rechazado' a 'rechazado/enRevision')"""
        print(f"📤 Petición de envío a revisión para solicitud: {solicitud_id}")
        conn = get_db_connection()
        if not conn:
            return jsonify({'error': 'Error de conexión a la base de datos'}), 500
        
        try:
            cur = conn.cursor()
            
            # Verificar que la solicitud existe y está rechazada
            cur.execute("SELECT estado, expediente_id FROM app.solicitudes WHERE id = %s", (solicitud_id,))
            solicitud = cur.fetchone()
            
            if not solicitud:
                cur.close()
                conn.close()
                print(f"❌ Solicitud {solicitud_id} no encontrada")
                return jsonify({'error': 'Solicitud no encontrada'}), 404
            
            estado_actual = solicitud[0]
            expediente_id = solicitud[1]
            
            print(f"📊 Estado actual de solicitud {solicitud_id}: '{estado_actual}'")
            
            # Solo aceptar 'rechazado' (no puede estar ya en revisión)
            if estado_actual != 'rechazado':
                cur.close()
                conn.close()
                print(f"⚠️ La solicitud no está en estado rechazado. Estado: '{estado_actual}'")
                return jsonify({'error': f'La solicitud debe estar rechazada para enviarla a revisión. Estado actual: {estado_actual}'}), 400
            
            # Cambiar estado de solicitud a 'rechazado/enRevision'
            print(f"🔄 Cambiando estado de 'rechazado' a 'rechazado/enRevision'...")
            cur.execute("""
                UPDATE app.solicitudes 
                SET estado = 'rechazado/enRevision'
                WHERE id = %s
            """, (solicitud_id,))
            
            if cur.rowcount == 0:
                print(f"⚠️ No se pudo actualizar solicitud {solicitud_id} - rowcount: {cur.rowcount}")
            else:
                print(f"✅ Solicitud {solicitud_id} actualizada - rowcount: {cur.rowcount}")
            
            # NO resetear items rechazados - mantener las observaciones para que jefatura vea qué se corrigió
            
            conn.commit()
            
            # Verificar que se guardó correctamente
            cur.execute("SELECT estado FROM app.solicitudes WHERE id = %s", (solicitud_id,))
            estado_verificado = cur.fetchone()[0]
            print(f"✅ Estado verificado después del commit: '{estado_verificado}'")
            
            cur.close()
            conn.close()
            
            return jsonify({
                'success': True,
                'message': 'Solicitud enviada a revisión exitosamente',
                'data': {
                    'solicitud_id': solicitud_id,
                    'estado': 'rechazado/enRevision',
                    'estado_anterior': estado_actual
                }
            }), 200
            
        except Exception as e:
            print(f'❌ Error enviando solicitud a revisión: {e}')
            import traceback
            print(traceback.format_exc())
            if 'conn' in locals():
                conn.rollback()
                conn.close()
            return jsonify({'error': f'Error interno del servidor: {str(e)}'}), 500

