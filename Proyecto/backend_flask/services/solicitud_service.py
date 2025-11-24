"""
Servicio para lógica de negocio de solicitudes
"""
def verificar_y_actualizar_estado_pendiente(expediente_id, solicitud_id, cur, conn):
    """Verificar si todas las firmas y el cálculo están completos, y actualizar estado a 'pendiente'"""
    try:
        print(f"🔍 Verificando si solicitud {solicitud_id} puede cambiar a 'pendiente'...")
        
        # 1. Verificar que el funcionario haya firmado
        cur.execute("""
            SELECT firmado_funcionario, estado 
            FROM app.solicitudes 
            WHERE id = %s
        """, (solicitud_id,))
        solicitud = cur.fetchone()
        
        if not solicitud:
            print(f"❌ Solicitud {solicitud_id} no encontrada")
            return False
        
        estado_actual = solicitud[1]
        firmado_funcionario = solicitud[0]
        
        print(f"📊 Estado actual: '{estado_actual}', Funcionario firmado: {firmado_funcionario}")
        
        if not firmado_funcionario:
            print(f"⏳ Solicitud {solicitud_id}: Funcionario aún no ha firmado")
            return False
        
        # 2. Verificar que todos los beneficiarios hayan firmado
        cur.execute("""
            SELECT 
                COUNT(b.id) as total_beneficiarios,
                COUNT(uf.id) as beneficiarios_firmados
            FROM app.beneficiarios b
            LEFT JOIN app.usuarios_firma uf ON b.ben_run = uf.rut
            WHERE b.expediente_id = %s
        """, (expediente_id,))
        
        firmas_result = cur.fetchone()
        total_beneficiarios = firmas_result[0] or 0
        beneficiarios_firmados = firmas_result[1] or 0
        
        print(f"📝 Beneficiarios: {beneficiarios_firmados}/{total_beneficiarios} firmados")
        
        if total_beneficiarios > 0 and beneficiarios_firmados < total_beneficiarios:
            print(f"⏳ Solicitud {solicitud_id}: Faltan firmas de beneficiarios ({beneficiarios_firmados}/{total_beneficiarios})")
            return False
        
        # 3. Verificar que el cálculo de saldo insoluto esté completo
        cur.execute("""
            SELECT id, estado, fecha_calculo
            FROM app.calculo_saldo_insoluto 
            WHERE expediente_id = %s AND estado IN ('pendiente', 'aprobado')
            ORDER BY fecha_calculo DESC, id DESC LIMIT 1
        """, (expediente_id,))
        
        calculo = cur.fetchone()
        if not calculo:
            cur.execute("""
                SELECT id, estado, fecha_calculo
                FROM app.calculo_saldo_insoluto 
                WHERE expediente_id = %s
                ORDER BY fecha_calculo DESC, id DESC LIMIT 1
            """, (expediente_id,))
            calculo_alternativo = cur.fetchone()
            if calculo_alternativo:
                print(f"⚠️ Solicitud {solicitud_id}: Cálculo encontrado pero con estado incorrecto")
                print(f"   Cálculo ID: {calculo_alternativo[0]}, Estado: '{calculo_alternativo[1]}'")
                print(f"   Se requiere estado 'pendiente' o 'aprobado'")
            else:
                print(f"⏳ Solicitud {solicitud_id}: No se encontró ningún cálculo de saldo insoluto para este expediente")
            return False
        
        print(f"💰 Cálculo encontrado: ID {calculo[0]}, Estado: '{calculo[1]}', Fecha: {calculo[2]}")
        
        # 4. Si todas las condiciones se cumplen, actualizar estado a 'pendiente'
        cur.execute("""
            UPDATE app.solicitudes 
            SET estado = 'pendiente'
            WHERE id = %s AND estado NOT IN ('pendiente', 'completado')
        """, (solicitud_id,))
        
        if cur.rowcount > 0:
            print(f"✅ Solicitud {solicitud_id} actualizada de '{estado_actual}' a 'pendiente' - Todas las firmas y cálculo completos")
            return True
        else:
            print(f"ℹ️ Solicitud {solicitud_id} no se actualizó. Estado actual: '{estado_actual}' (puede estar en estado final)")
            return False
            
    except Exception as e:
        print(f"⚠️ Error verificando estado pendiente: {e}")
        import traceback
        print(traceback.format_exc())
        return False

