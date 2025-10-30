#!/usr/bin/env python3
import bcrypt
import psycopg2
from psycopg2.extras import RealDictCursor
from config import Config

def update_password():
    # Generar hash para Admin1234
    password = "Admin1234"
    new_hash = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
    
    print(f"🔧 Generando hash para: {password}")
    print(f"🔧 Nuevo hash: {new_hash}")
    print()
    
    # Conectar a la base de datos
    try:
        config = Config()
        conn = psycopg2.connect(**config.DATABASE_CONFIG)
        cur = conn.cursor()
        
        # Actualizar password para Sebastian Madrid
        rut_sebastian = "17.518.203-9"
        cur.execute("""
            UPDATE app.funcionarios 
            SET password_hash = %s
            WHERE rut = %s
        """, (new_hash, rut_sebastian))
        
        if cur.rowcount > 0:
            print(f"✅ Password actualizado para RUT: {rut_sebastian}")
            print(f"✅ Nueva contraseña: {password}")
        else:
            print(f"❌ No se encontró funcionario con RUT: {rut_sebastian}")
        
        # Actualizar password para Jose Antonio (opcional)
        rut_jose = "18.075.712-0"
        cur.execute("""
            UPDATE app.funcionarios 
            SET password_hash = %s
            WHERE rut = %s
        """, (new_hash, rut_jose))
        
        if cur.rowcount > 0:
            print(f"✅ Password actualizado para RUT: {rut_jose}")
            print(f"✅ Nueva contraseña: {password}")
        else:
            print(f"❌ No se encontró funcionario con RUT: {rut_jose}")
        
        conn.commit()
        cur.close()
        conn.close()
        
        print()
        print("=" * 50)
        print("✅ ACTUALIZACIÓN COMPLETADA")
        print("=" * 50)
        print("Credenciales para login:")
        print(f"RUT: {rut_sebastian}")
        print(f"Password: {password}")
        print()
        print("O también:")
        print(f"RUT: {rut_jose}")
        print(f"Password: {password}")
        
    except Exception as e:
        print(f"❌ Error actualizando password: {e}")

if __name__ == "__main__":
    update_password()
















