#!/usr/bin/env python3
"""
Script de prueba de conexión a PostgreSQL
Este script verifica que la conexión a la base de datos esté configurada correctamente
"""

import sys
import os

# Agregar el directorio padre al path para importar config
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    import psycopg2
    from psycopg2.extras import RealDictCursor
    from config import Config
except ImportError as e:
    print(f"❌ Error importando módulos: {e}")
    print("💡 Asegúrate de instalar las dependencias:")
    print("   pip install -r requirements.txt")
    sys.exit(1)


def test_connection():
    """Probar la conexión a PostgreSQL"""
    print("=" * 60)
    print("🔍 Probando conexión a PostgreSQL")
    print("=" * 60)
    
    # Obtener configuración
    config = Config()
    db_config = config.DATABASE_CONFIG
    
    print("\n📋 Configuración de conexión:")
    print(f"   Host: {db_config['host']}")
    print(f"   Port: {db_config['port']}")
    print(f"   Database: {db_config['database']}")
    print(f"   User: {db_config['user']}")
    print(f"   Password: {'*' * len(db_config['password'])}")
    
    # Intentar conectar
    print("\n🔄 Intentando conectar...")
    try:
        conn = psycopg2.connect(**db_config)
        print("✅ ¡Conexión exitosa!")
        
        # Obtener información del servidor
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        # Versión de PostgreSQL
        cur.execute("SELECT version();")
        version = cur.fetchone()['version']
        print(f"\n📦 Versión de PostgreSQL:")
        print(f"   {version}")
        
        # Hora del servidor
        cur.execute("SELECT NOW() as server_time;")
        server_time = cur.fetchone()['server_time']
        print(f"\n📅 Hora del servidor:")
        print(f"   {server_time}")
        
        # Verificar esquema app
        cur.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.schemata 
                WHERE schema_name = 'app'
            ) as schema_exists;
        """)
        schema_exists = cur.fetchone()['schema_exists']
        
        if schema_exists:
            print("\n✅ Esquema 'app' encontrado")
            
            # Contar tablas en el esquema app
            cur.execute("""
                SELECT COUNT(*) as table_count
                FROM information_schema.tables
                WHERE table_schema = 'app';
            """)
            table_count = cur.fetchone()['table_count']
            print(f"   📊 Número de tablas: {table_count}")
            
            # Listar tablas
            if table_count > 0:
                cur.execute("""
                    SELECT table_name
                    FROM information_schema.tables
                    WHERE table_schema = 'app'
                    ORDER BY table_name;
                """)
                tables = cur.fetchall()
                print("\n📋 Tablas encontradas:")
                for table in tables:
                    print(f"   - {table['table_name']}")
            else:
                print("   ⚠️  No se encontraron tablas en el esquema 'app'")
                print("   💡 Ejecuta el script init_database.sql para crear las tablas")
        else:
            print("\n❌ Esquema 'app' no encontrado")
            print("   💡 Ejecuta el script init_database.sql para crear el esquema")
        
        # Verificar usuario administrador
        cur.execute("""
            SELECT COUNT(*) as admin_count
            FROM app.funcionarios
            WHERE rut = '12345678-9';
        """)
        admin_count = cur.fetchone()['admin_count']
        
        if admin_count > 0:
            print("\n✅ Usuario administrador encontrado")
            print("   RUT: 12345678-9")
            print("   Password: admin123")
        else:
            print("\n⚠️  Usuario administrador no encontrado")
            print("   💡 Ejecuta el script init_database.sql para crear el usuario")
        
        cur.close()
        conn.close()
        
        print("\n" + "=" * 60)
        print("✅ Todas las pruebas pasaron exitosamente")
        print("=" * 60)
        return True
        
    except psycopg2.OperationalError as e:
        print(f"\n❌ Error de conexión: {e}")
        print("\n💡 Posibles soluciones:")
        print("   1. Verifica que PostgreSQL esté corriendo")
        print("   2. Revisa las credenciales en config.env")
        print("   3. Verifica el puerto de PostgreSQL")
        print("   4. Asegúrate de que la base de datos exista")
        return False
        
    except psycopg2.ProgrammingError as e:
        print(f"\n❌ Error de programación: {e}")
        print("\n💡 Posibles soluciones:")
        print("   1. Ejecuta el script init_database.sql")
        print("   2. Verifica que el esquema 'app' exista")
        return False
        
    except Exception as e:
        print(f"\n❌ Error inesperado: {e}")
        print(f"   Tipo: {type(e).__name__}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == '__main__':
    success = test_connection()
    sys.exit(0 if success else 1)


