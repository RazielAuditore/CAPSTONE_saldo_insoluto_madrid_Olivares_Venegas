"""Script para agregar 'pendiente' al ENUM app.estado_solicitud"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from utils.database import get_db_connection

def agregar_pendiente_enum():
    conn = get_db_connection()
    if not conn:
        print("ERROR: No se pudo conectar a la base de datos")
        return False
    
    try:
        cur = conn.cursor()
        
        # Verificar si 'pendiente' ya existe
        cur.execute("""
            SELECT unnest(enum_range(NULL::app.estado_solicitud)) AS valor
        """)
        valores_existentes = [row[0] for row in cur.fetchall()]
        
        if 'pendiente' in valores_existentes:
            print("'pendiente' ya existe en el ENUM")
            cur.close()
            conn.close()
            return True
        
        # Agregar 'pendiente' al ENUM
        print("Agregando 'pendiente' al ENUM app.estado_solicitud...")
        cur.execute("ALTER TYPE app.estado_solicitud ADD VALUE 'pendiente'")
        
        conn.commit()
        
        # Verificar que se agregó
        cur.execute("""
            SELECT unnest(enum_range(NULL::app.estado_solicitud)) AS valor
            ORDER BY valor
        """)
        valores_nuevos = [row[0] for row in cur.fetchall()]
        
        print("\nValores del ENUM app.estado_solicitud (actualizados):")
        print("-" * 50)
        for valor in valores_nuevos:
            print(f"  - {valor}")
        print("-" * 50)
        
        if 'pendiente' in valores_nuevos:
            print("\nSUCCESS: 'pendiente' agregado exitosamente al ENUM")
            cur.close()
            conn.close()
            return True
        else:
            print("\nERROR: No se pudo verificar que 'pendiente' se agregó")
            cur.close()
            conn.close()
            return False
        
    except Exception as e:
        print(f"ERROR: Error agregando valor al ENUM: {e}")
        if 'conn' in locals():
            conn.rollback()
            conn.close()
        return False

if __name__ == "__main__":
    agregar_pendiente_enum()




