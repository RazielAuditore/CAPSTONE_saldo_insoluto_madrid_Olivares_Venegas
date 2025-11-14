"""Script para agregar 'rechazado' y 'rechazado/enRevision' al ENUM app.estado_solicitud"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from utils.database import get_db_connection

def agregar_rechazado_enum():
    conn = get_db_connection()
    if not conn:
        print("ERROR: No se pudo conectar a la base de datos")
        return False
    
    try:
        cur = conn.cursor()
        
        # Verificar valores existentes
        cur.execute("""
            SELECT unnest(enum_range(NULL::app.estado_solicitud)) AS valor
        """)
        valores_existentes = [row[0] for row in cur.fetchall()]
        
        print("\nValores actuales del ENUM app.estado_solicitud:")
        print("-" * 50)
        for valor in valores_existentes:
            print(f"  - {valor}")
        print("-" * 50)
        
        valores_agregados = []
        
        # Agregar 'rechazado' si no existe
        if 'rechazado' not in valores_existentes:
            print("\nAgregando 'rechazado' al ENUM app.estado_solicitud...")
            try:
                cur.execute("ALTER TYPE app.estado_solicitud ADD VALUE 'rechazado'")
                valores_agregados.append('rechazado')
                print("✅ 'rechazado' agregado exitosamente")
            except Exception as e:
                print(f"⚠️ Error agregando 'rechazado': {e}")
        else:
            print("ℹ️ 'rechazado' ya existe en el ENUM")
        
        # Agregar 'rechazado/enRevision' si no existe
        if 'rechazado/enRevision' not in valores_existentes:
            print("\nAgregando 'rechazado/enRevision' al ENUM app.estado_solicitud...")
            try:
                cur.execute("ALTER TYPE app.estado_solicitud ADD VALUE 'rechazado/enRevision'")
                valores_agregados.append('rechazado/enRevision')
                print("✅ 'rechazado/enRevision' agregado exitosamente")
            except Exception as e:
                print(f"⚠️ Error agregando 'rechazado/enRevision': {e}")
        else:
            print("ℹ️ 'rechazado/enRevision' ya existe en el ENUM")
        
        conn.commit()
        
        # Verificar valores finales
        cur.execute("""
            SELECT unnest(enum_range(NULL::app.estado_solicitud)) AS valor
            ORDER BY valor
        """)
        valores_finales = [row[0] for row in cur.fetchall()]
        
        print("\n" + "=" * 60)
        print("Valores FINALES del ENUM app.estado_solicitud:")
        print("=" * 60)
        for valor in valores_finales:
            marcador = " ✅ NUEVO" if valor in valores_agregados else ""
            print(f"  - {valor}{marcador}")
        print("=" * 60)
        
        # Verificar que ambos valores estén presentes
        if 'rechazado' in valores_finales and 'rechazado/enRevision' in valores_finales:
            print("\n✅ SUCCESS: Ambos valores agregados exitosamente al ENUM")
            cur.close()
            conn.close()
            return True
        else:
            faltantes = []
            if 'rechazado' not in valores_finales:
                faltantes.append('rechazado')
            if 'rechazado/enRevision' not in valores_finales:
                faltantes.append('rechazado/enRevision')
            print(f"\n⚠️ WARNING: Faltan valores en el ENUM: {', '.join(faltantes)}")
            cur.close()
            conn.close()
            return False
        
    except Exception as e:
        print(f"\n❌ ERROR: Error agregando valores al ENUM: {e}")
        import traceback
        print(traceback.format_exc())
        if 'conn' in locals():
            conn.rollback()
            conn.close()
        return False

if __name__ == "__main__":
    print("=" * 60)
    print("Agregando 'rechazado' y 'rechazado/enRevision' al ENUM")
    print("=" * 60)
    agregar_rechazado_enum()

