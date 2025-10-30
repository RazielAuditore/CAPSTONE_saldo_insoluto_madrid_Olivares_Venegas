"""
Funciones de conexión y manejo de base de datos
"""
import psycopg2
from psycopg2.extras import RealDictCursor
from config import Config

# Configuración de la base de datos
DB_CONFIG = Config().DATABASE_CONFIG

def get_db_connection():
    """Obtener conexión a la base de datos"""
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        return conn
    except Exception as e:
        print(f"❌ Error conectando a PostgreSQL: {e}")
        return None

def test_connection():
    """Probar la conexión a la base de datos"""
    conn = get_db_connection()
    if conn:
        try:
            cur = conn.cursor()
            cur.execute('SELECT NOW()')
            result = cur.fetchone()
            print('✅ Conectado a PostgreSQL')
            print(f'📅 Hora del servidor: {result[0]}')
            cur.close()
            conn.close()
            return True
        except Exception as e:
            print(f'❌ Error en consulta de prueba: {e}')
            return False
    return False

def create_firmas_beneficiarios_table():
    """Crear tabla para almacenar firmas de beneficiarios"""
    from utils.helpers import hash_password
    
    conn = get_db_connection()
    if not conn:
        print("❌ No se pudo conectar a la base de datos")
        return False
    
    try:
        cur = conn.cursor()
        
        # Crear tabla firmas_beneficiarios
        cur.execute("""
            CREATE TABLE IF NOT EXISTS app.firmas_beneficiarios (
                id SERIAL PRIMARY KEY,
                expediente_id INTEGER NOT NULL REFERENCES app.expediente(id) ON DELETE CASCADE,
                beneficiario_id INTEGER NOT NULL REFERENCES app.beneficiarios(id) ON DELETE CASCADE,
                firma_hash VARCHAR(255) NOT NULL,
                fecha_firma TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                estado VARCHAR(50) DEFAULT 'activa',
                observaciones TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Agregar campo funcionario_id a tabla expediente si no existe
        cur.execute("""
            ALTER TABLE app.expediente 
            ADD COLUMN IF NOT EXISTS funcionario_id INTEGER
        """)
        
        # Verificar que existe la tabla funcionarios
        cur.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_schema = 'app' 
                AND table_name = 'funcionarios'
            )
        """)
        
        tabla_funcionarios_existe = cur.fetchone()[0]
        
        if tabla_funcionarios_existe:
            print('✅ Tabla funcionarios encontrada')
        else:
            print('⚠️ Tabla funcionarios no encontrada - creando tabla básica')
            # Crear tabla funcionarios básica si no existe
            cur.execute("""
                CREATE TABLE IF NOT EXISTS app.funcionarios (
                    id SERIAL PRIMARY KEY,
                    rut VARCHAR(20) UNIQUE NOT NULL,
                    nombres VARCHAR(100) NOT NULL,
                    apellido_p VARCHAR(100) NOT NULL,
                    apellido_m VARCHAR(100),
                    password_hash VARCHAR(255) NOT NULL,
                    rol VARCHAR(50) DEFAULT 'funcionario',
                    sucursal VARCHAR(100),
                    iniciales VARCHAR(10),
                    activo BOOLEAN DEFAULT true,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Crear funcionario de prueba si no existe
            cur.execute("""
                INSERT INTO app.funcionarios (rut, nombres, apellido_p, password_hash, rol, sucursal, iniciales) 
                SELECT '12345678-9', 'Admin', 'Sistema', %s, 'administrador', 'Central', 'AS'
                WHERE NOT EXISTS (SELECT 1 FROM app.funcionarios WHERE rut = '12345678-9')
            """, (hash_password('admin123'),))
        
        # Crear índices para optimizar consultas
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_firmas_beneficiarios_expediente 
            ON app.firmas_beneficiarios(expediente_id)
        """)
        
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_firmas_beneficiarios_beneficiario 
            ON app.firmas_beneficiarios(beneficiario_id)
        """)
        
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_firmas_beneficiarios_estado 
            ON app.firmas_beneficiarios(estado)
        """)
        
        # Crear índice único para evitar firmas duplicadas
        cur.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS idx_firmas_beneficiarios_unique 
            ON app.firmas_beneficiarios(expediente_id, beneficiario_id) 
            WHERE estado = 'activa'
        """)
        
        conn.commit()
        cur.close()
        conn.close()
        
        print('✅ Tabla firmas_beneficiarios creada exitosamente')
        print('✅ Campo funcionario_id agregado a tabla expediente')
        print('✅ Tabla funcionarios verificada/creada')
        print('✅ Funcionario admin creado (RUT: 12345678-9, password: admin123)')
        print('✅ Índices optimizados creados')
        return True
        
    except Exception as e:
        print(f'❌ Error creando tabla firmas_beneficiarios: {e}')
        if conn:
            conn.rollback()
            conn.close()
        return False


