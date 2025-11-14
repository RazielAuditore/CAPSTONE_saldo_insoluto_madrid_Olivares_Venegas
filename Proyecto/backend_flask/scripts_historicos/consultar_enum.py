"""Script para consultar valores del ENUM app.estado_solicitud"""
import sys
import os

# Agregar el directorio padre al path para importar utils
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from utils.database import get_db_connection

def consultar_enum():
    conn = get_db_connection()
    if not conn:
        print("ERROR: No se pudo conectar a la base de datos")
        return
    
    try:
        cur = conn.cursor()
        
        # Consultar valores del ENUM
        cur.execute("""
            SELECT unnest(enum_range(NULL::app.estado_solicitud)) AS valor
            ORDER BY valor;
        """)
        
        valores = cur.fetchall()
        
        if valores:
            print("\nValores del ENUM app.estado_solicitud:")
            print("-" * 50)
            for valor in valores:
                print(f"  - {valor[0]}")
            print("-" * 50)
            print(f"\nTotal: {len(valores)} valores")
        else:
            print("ADVERTENCIA: No se encontraron valores o el ENUM no existe")
            
            # Intentar verificar si la columna existe y qué tipo tiene
            cur.execute("""
                SELECT data_type, udt_name 
                FROM information_schema.columns 
                WHERE table_schema = 'app' 
                AND table_name = 'solicitudes' 
                AND column_name = 'estado'
            """)
            
            tipo_columna = cur.fetchone()
            if tipo_columna:
                print(f"\nTipo de columna 'estado': {tipo_columna[0]} ({tipo_columna[1]})")
        
        cur.close()
        conn.close()
        
    except Exception as e:
        print(f"ERROR: Error consultando ENUM: {e}")
        if 'conn' in locals():
            conn.close()

if __name__ == "__main__":
    consultar_enum()

