"""
Rutas de gestión de cálculos de saldo insoluto
"""
from flask import request, jsonify, session
from psycopg2.extras import RealDictCursor
from utils.database import get_db_connection
from middleware.auth import login_required
from services.solicitud_service import verificar_y_actualizar_estado_pendiente

def register_routes(app):
    """Registrar rutas de cálculos"""
    
    @app.route('/api/calcular-saldo-insoluto', methods=['POST'])
    @login_required
    def guardar_calculo_saldo():
        """Guardar cálculo de saldo insoluto"""
        conn = get_db_connection()
        if not conn:
            return jsonify({'error': 'Error de conexión a la base de datos'}), 500
        
        try:
            data = request.get_json()
            expediente_id = data.get('expediente_id')
            solicitud_id = data.get('solicitud_id')
            beneficios = data.get('beneficios', [])  # Array de {codigo, nombre, monto}
            total = data.get('total')
            
            if not expediente_id or not beneficios or not total:
                return jsonify({'error': 'Datos incompletos'}), 400
            
            cur = conn.cursor()
            funcionario_id = session.get('user_id')
            
            # Verificar estado de la solicitud para bloquear si está en pendiente
            if solicitud_id:
                cur.execute("""
                    SELECT estado FROM app.solicitudes WHERE id = %s
                """, (solicitud_id,))
                solicitud_result = cur.fetchone()
                if solicitud_result and solicitud_result[0] == 'pendiente':
                    return jsonify({
                        'error': 'No se puede calcular o recalcular el saldo insoluto de un expediente que está en revisión de jefatura. Debe estar rechazado para poder recalcular.'
                    }), 400
            
            # Verificar si ya existe un cálculo activo (pendiente o aprobado)
            cur.execute("""
                SELECT id, estado FROM app.calculo_saldo_insoluto 
                WHERE expediente_id = %s AND estado IN ('pendiente', 'aprobado')
                ORDER BY fecha_calculo DESC LIMIT 1
            """, (expediente_id,))
            
            calculo_existente = cur.fetchone()
            if calculo_existente:
                # Verificar si el expediente está rechazado/enRevision para permitir modificar
                cur.execute("""
                    SELECT estado FROM app.solicitudes 
                    WHERE expediente_id = %s 
                    ORDER BY id DESC LIMIT 1
                """, (expediente_id,))
                solicitud_estado = cur.fetchone()
                if not solicitud_estado or solicitud_estado[0] != 'rechazado/enRevision':
                    return jsonify({
                        'error': f'Ya existe un cálculo {calculo_existente[1]} para este expediente. Solo se puede recalcular si el expediente fue rechazado.'
                    }), 400
            
            # Si existe un cálculo rechazado y el expediente está en revisión, actualizar en lugar de crear nuevo
            calculo_id = None
            if calculo_existente:
                calculo_id = calculo_existente[0]
                # Actualizar cálculo existente
                cur.execute("""
                    UPDATE app.calculo_saldo_insoluto 
                    SET total_calculado = %s,
                        calculado_por = %s,
                        estado = 'pendiente',
                        fecha_calculo = NOW()
                    WHERE id = %s
                """, (total, funcionario_id, calculo_id))
                
                # Eliminar detalles antiguos
                cur.execute("DELETE FROM app.detalle_calculo_saldo WHERE calculo_id = %s", (calculo_id,))
            else:
                # Insertar cálculo principal
                cur.execute("""
                    INSERT INTO app.calculo_saldo_insoluto 
                    (expediente_id, solicitud_id, total_calculado, calculado_por, estado)
                    VALUES (%s, %s, %s, %s, 'pendiente')
                    RETURNING id
                """, (expediente_id, solicitud_id, total, funcionario_id))
                calculo_id = cur.fetchone()[0]
            
            # Insertar detalles de beneficios (tanto para nuevo como para actualizado)
            for beneficio in beneficios:
                cur.execute("""
                    INSERT INTO app.detalle_calculo_saldo 
                    (calculo_id, beneficio_codigo, beneficio_nombre, monto)
                    VALUES (%s, %s, %s, %s)
                """, (calculo_id, beneficio.get('codigo'), beneficio.get('nombre'), beneficio.get('monto')))
            
            print(f"✅ Cálculo guardado: ID {calculo_id}, Total: {total}")
            
            # Verificar si la solicitud está lista para evaluación (todas las firmas + cálculo)
            # IMPORTANTE: Verificar DESPUÉS de insertar el cálculo para que lo encuentre
            estado_actualizado = False
            if solicitud_id:
                print(f"\n{'='*60}")
                print(f"🔍 INICIANDO VERIFICACIÓN DE ESTADO PARA SOLICITUD {solicitud_id}")
                print(f"{'='*60}\n")
                resultado_verificacion = verificar_y_actualizar_estado_pendiente(expediente_id, solicitud_id, cur, conn)
                print(f"\n{'='*60}")
                if resultado_verificacion:
                    print(f"✅ RESULTADO: Solicitud {solicitud_id} BLOQUEADA - Estado actualizado a 'pendiente'")
                    estado_actualizado = True
                else:
                    print(f"❌ RESULTADO: Solicitud {solicitud_id} NO se pudo actualizar a 'pendiente'")
                    print(f"   Revisa los mensajes anteriores para ver qué condición no se cumplió")
                print(f"{'='*60}\n")
            else:
                print(f"⚠️ No se proporcionó solicitud_id, no se puede verificar estado")
            
            conn.commit()
            cur.close()
            conn.close()
            
            return jsonify({
                'success': True,
                'message': 'Cálculo guardado exitosamente',
                'data': {
                    'calculo_id': calculo_id,
                    'expediente_id': expediente_id,
                    'total': total,
                    'estado_actualizado': estado_actualizado
                }
            }), 201
            
        except Exception as e:
            print(f'❌ Error guardando cálculo: {e}')
            if 'conn' in locals():
                conn.rollback()
                conn.close()
            return jsonify({'error': f'Error interno del servidor: {str(e)}'}), 500

    @app.route('/api/expediente/<int:expediente_id>/calculo-existente', methods=['GET'])
    @login_required
    def verificar_calculo_existente(expediente_id):
        """Verificar si existe un cálculo activo para un expediente"""
        conn = get_db_connection()
        if not conn:
            return jsonify({'error': 'Error de conexión a la base de datos'}), 500
        
        try:
            cur = conn.cursor(cursor_factory=RealDictCursor)
            
            # Buscar cálculo activo (pendiente o aprobado)
            cur.execute("""
                SELECT id, estado, total_calculado, fecha_calculo 
                FROM app.calculo_saldo_insoluto 
                WHERE expediente_id = %s AND estado IN ('pendiente', 'aprobado')
                ORDER BY fecha_calculo DESC LIMIT 1
            """, (expediente_id,))
            
            calculo = cur.fetchone()
            
            cur.close()
            conn.close()
            
            if calculo:
                return jsonify({
                    'existe': True,
                    'calculo': {
                        'id': calculo['id'],
                        'estado': calculo['estado'],
                        'total_calculado': float(calculo['total_calculado']),
                        'fecha_calculo': calculo['fecha_calculo'].isoformat() if calculo['fecha_calculo'] else None
                    }
                }), 200
            else:
                return jsonify({
                    'existe': False
                }), 200
            
        except Exception as e:
            print(f'❌ Error verificando cálculo: {e}')
            if 'conn' in locals():
                conn.close()
            return jsonify({'error': f'Error interno del servidor: {str(e)}'}), 500

    @app.route('/api/expediente/<int:expediente_id>/calculo-completo', methods=['GET'])
    @login_required
    def obtener_calculo_completo(expediente_id):
        """Obtener cálculo completo de saldo insoluto con detalles de beneficios"""
        conn = get_db_connection()
        if not conn:
            return jsonify({'error': 'Error de conexión a la base de datos'}), 500
        
        try:
            cur = conn.cursor(cursor_factory=RealDictCursor)
            
            # Buscar cálculo activo (pendiente o aprobado)
            cur.execute("""
                SELECT 
                    c.id,
                    c.estado,
                    c.total_calculado,
                    c.fecha_calculo,
                    c.solicitud_id,
                    c.calculado_por,
                    f.nombres || ' ' || f.apellido_p as funcionario_nombre
                FROM app.calculo_saldo_insoluto c
                LEFT JOIN app.funcionarios f ON c.calculado_por = f.id
                WHERE c.expediente_id = %s AND c.estado IN ('pendiente', 'aprobado')
                ORDER BY c.fecha_calculo DESC LIMIT 1
            """, (expediente_id,))
            
            calculo = cur.fetchone()
            
            if not calculo:
                cur.close()
                conn.close()
                return jsonify({
                    'existe': False,
                    'message': 'No existe cálculo para este expediente'
                }), 200
            
            # Obtener detalles de beneficios
            cur.execute("""
                SELECT 
                    beneficio_codigo,
                    beneficio_nombre,
                    monto
                FROM app.detalle_calculo_saldo
                WHERE calculo_id = %s
                ORDER BY beneficio_codigo
            """, (calculo['id'],))
            
            detalles = cur.fetchall()
            
            cur.close()
            conn.close()
            
            return jsonify({
                'existe': True,
                'calculo': {
                    'id': calculo['id'],
                    'estado': calculo['estado'],
                    'total_calculado': float(calculo['total_calculado']),
                    'fecha_calculo': calculo['fecha_calculo'].isoformat() if calculo['fecha_calculo'] else None,
                    'solicitud_id': calculo['solicitud_id'],
                    'calculado_por': calculo['calculado_por'],
                    'funcionario_nombre': calculo['funcionario_nombre'],
                    'beneficios': [
                        {
                            'codigo': det['beneficio_codigo'],
                            'nombre': det['beneficio_nombre'],
                            'monto': float(det['monto'])
                        }
                        for det in detalles
                    ]
                }
            }), 200
            
        except Exception as e:
            print(f'❌ Error obteniendo cálculo completo: {e}')
            if 'conn' in locals():
                conn.close()
            return jsonify({'error': f'Error interno del servidor: {str(e)}'}), 500

