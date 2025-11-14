"""
Script para ejecutar directamente SQL y verificar/fijar las columnas
Ejecuta este script Python independiente
"""
from utils.database import get_db_connection

def fix_and_test():
    conn = get_db_connection()
    if not conn:
        print("❌ No se pudo conectar")
        return
    
    cur = conn.cursor()
    
    try:
        # 1. Crear columnas si no existen
        print("1. Creando columnas...")
        cur.execute("ALTER TABLE app.solicitudes ADD COLUMN IF NOT EXISTS firmado_funcionario BOOLEAN DEFAULT FALSE")
        cur.execute("ALTER TABLE app.solicitudes ADD COLUMN IF NOT EXISTS fecha_firma_funcionario TIMESTAMP")
        cur.execute("ALTER TABLE app.solicitudes ADD COLUMN IF NOT EXISTS funcionario_id_firma INTEGER REFERENCES app.funcionarios(id) ON DELETE SET NULL")
        
        # 2. Verificar que existen
        print("2. Verificando columnas...")
        cur.execute("""
            SELECT column_name FROM information_schema.columns 
            WHERE table_schema = 'app' AND table_name = 'solicitudes' 
            AND column_name IN ('firmado_funcionario', 'fecha_firma_funcionario', 'funcionario_id_firma')
        """)
        cols = [row[0] for row in cur.fetchall()]
        print(f"   Columnas encontradas: {cols}")
        
        # 3. Probar UPDATE en una solicitud de prueba
        print("3. Probando UPDATE...")
        cur.execute("SELECT id FROM app.solicitudes LIMIT 1")
        solicitud_test = cur.fetchone()
        if solicitud_test:
            solicitud_id = solicitud_test[0]
            print(f"   Probando con solicitud ID: {solicitud_id}")
            cur.execute("""
                UPDATE app.solicitudes 
                SET firmado_funcionario = TRUE,
                    fecha_firma_funcionario = NOW(),
                    funcionario_id_firma = 2
                WHERE id = %s
            """, (solicitud_id,))
            print(f"   Rowcount: {cur.rowcount}")
            
            if cur.rowcount > 0:
                conn.commit()
                print("   ✅ UPDATE exitoso, haciendo commit...")
                
                # Verificar
                cur.execute("SELECT firmado_funcionario, fecha_firma_funcionario, funcionario_id_firma FROM app.solicitudes WHERE id = %s", (solicitud_id,))
                resultado = cur.fetchone()
                print(f"   Verificación: firmado={resultado[0]}, fecha={resultado[1]}, funcionario_id={resultado[2]}")
            else:
                print("   ❌ UPDATE no afectó filas")
        else:
            print("   ⚠️ No hay solicitudes para probar")
        
        conn.commit()
        print("✅ Script completado")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        conn.rollback()
    finally:
        cur.close()
        conn.close()

if __name__ == '__main__':
    fix_and_test()




