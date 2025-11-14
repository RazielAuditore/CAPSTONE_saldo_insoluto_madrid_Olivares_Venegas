"""Script para ejecutar el SQL y agregar 'rechazado' y 'rechazado/enRevision' al ENUM"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from utils.database import get_db_connection

def ejecutar_agregar_rechazado():
    conn = get_db_connection()
    if not conn:
        print("ERROR: No se pudo conectar a la base de datos")
        return False
    
    try:
        cur = conn.cursor()
        
        # Verificar valores actuales
        cur.execute("""
            SELECT unnest(enum_range(NULL::app.estado_solicitud)) AS valor
            ORDER BY valor
        """)
        valores_actuales = [row[0] for row in cur.fetchall()]
        
        print("\nValores actuales del ENUM app.estado_solicitud:")
        print("-" * 50)
        for valor in valores_actuales:
            print(f"  - {valor}")
        print("-" * 50)
        
        valores_agregados = []
        
        # Agregar 'rechazado' si no existe
        if 'rechazado' not in valores_actuales:
            print("\nAgregando 'rechazado' al ENUM...")
            try:
                cur.execute("ALTER TYPE app.estado_solicitud ADD VALUE 'rechazado'")
                valores_agregados.append('rechazado')
                print("OK: 'rechazado' agregado exitosamente")
            except Exception as e:
                print(f"ERROR agregando 'rechazado': {e}")
        else:
            print("\n'rechazado' ya existe en el ENUM")
        
        # Agregar 'rechazado/enRevision' si no existe
        if 'rechazado/enRevision' not in valores_actuales:
            print("\nAgregando 'rechazado/enRevision' al ENUM...")
            try:
                cur.execute("ALTER TYPE app.estado_solicitud ADD VALUE 'rechazado/enRevision'")
                valores_agregados.append('rechazado/enRevision')
                print("OK: 'rechazado/enRevision' agregado exitosamente")
            except Exception as e:
                print(f"ERROR agregando 'rechazado/enRevision': {e}")
        else:
            print("\n'rechazado/enRevision' ya existe en el ENUM")
        
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
            marcador = " [NUEVO]" if valor in valores_agregados else ""
            print(f"  - {valor}{marcador}")
        print("=" * 60)
        
        if 'rechazado' in valores_finales and 'rechazado/enRevision' in valores_finales:
            print("\nSUCCESS: Ambos valores agregados exitosamente al ENUM")
            cur.close()
            conn.close()
            return True
        else:
            faltantes = []
            if 'rechazado' not in valores_finales:
                faltantes.append('rechazado')
            if 'rechazado/enRevision' not in valores_finales:
                faltantes.append('rechazado/enRevision')
            print(f"\nWARNING: Faltan valores en el ENUM: {', '.join(faltantes)}")
            cur.close()
            conn.close()
            return False
        
    except Exception as e:
        print(f"\nERROR: Error agregando valores al ENUM: {e}")
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
    ejecutar_agregar_rechazado()

