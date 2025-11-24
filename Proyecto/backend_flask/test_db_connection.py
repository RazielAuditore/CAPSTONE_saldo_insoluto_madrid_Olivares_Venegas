#!/usr/bin/env python3
"""
Script rápido para probar la conexión a PostgreSQL
"""

import sys
import os

# Agregar el directorio actual al path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from config import Config
    import psycopg2
    from psycopg2.extras import RealDictCursor
except ImportError as e:
    print(f"❌ Error importando módulos: {e}")
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
    print(f"   Password: {'*' * len(db_config['password']) if db_config['password'] else 'NO DEFINIDA'}")
    
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
        print(f"   {version.split(',')[0]}")
        
        # Hora del servidor
        cur.execute("SELECT NOW() as server_time;")
        server_time = cur.fetchone()['server_time']
        print(f"\n📅 Hora del servidor: {server_time}")
        
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
            print("\n⚠️  Esquema 'app' no encontrado")
            print("   💡 Necesitas ejecutar un script SQL para crear el esquema y las tablas")
            print("   💡 Puedes usar pgAdmin4 para ejecutar el script de inicialización")
        
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
        print("   2. Verifica el puerto: Por defecto es 5432")
        print("   3. Revisa las credenciales en config.env")
        print("   4. Asegúrate de que la base de datos 'postgres' exista")
        print("\n📝 Para verificar en pgAdmin4:")
        print("   - Abre pgAdmin4")
        print("   - Conéctate al servidor PostgreSQL")
        print("   - Verifica que puedas ver la base de datos 'postgres'")
        return False
        
    except psycopg2.ProgrammingError as e:
        print(f"\n❌ Error de programación: {e}")
        print("\n💡 Posibles soluciones:")
        print("   1. Ejecuta el script init_database.sql en pgAdmin4")
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


