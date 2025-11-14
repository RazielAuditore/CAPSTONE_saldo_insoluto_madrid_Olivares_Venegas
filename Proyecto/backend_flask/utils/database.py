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

def create_calculo_saldo_insoluto_tables():
    """Crear tablas para almacenar cálculos de saldo insoluto"""
    conn = get_db_connection()
    if not conn:
        print("❌ No se pudo conectar a la base de datos")
        return False
    
    try:
        cur = conn.cursor()
        
        # Crear tabla calculo_saldo_insoluto
        cur.execute("""
            CREATE TABLE IF NOT EXISTS app.calculo_saldo_insoluto (
                id SERIAL PRIMARY KEY,
                expediente_id INTEGER NOT NULL REFERENCES app.expediente(id) ON DELETE CASCADE,
                solicitud_id INTEGER REFERENCES app.solicitudes(id) ON DELETE SET NULL,
                total_calculado DECIMAL(15,2) NOT NULL,
                fecha_calculo TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                calculado_por INTEGER REFERENCES app.funcionarios(id) ON DELETE SET NULL,
                estado VARCHAR(50) DEFAULT 'pendiente',
                observaciones TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Crear tabla detalle_calculo_saldo
        cur.execute("""
            CREATE TABLE IF NOT EXISTS app.detalle_calculo_saldo (
                id SERIAL PRIMARY KEY,
                calculo_id INTEGER NOT NULL REFERENCES app.calculo_saldo_insoluto(id) ON DELETE CASCADE,
                beneficio_codigo INTEGER NOT NULL,
                beneficio_nombre VARCHAR(255) NOT NULL,
                monto DECIMAL(15,2) NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Crear índices para optimizar consultas
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_calculo_saldo_expediente 
            ON app.calculo_saldo_insoluto(expediente_id)
        """)
        
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_calculo_saldo_solicitud 
            ON app.calculo_saldo_insoluto(solicitud_id)
        """)
        
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_calculo_saldo_estado 
            ON app.calculo_saldo_insoluto(estado)
        """)
        
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_detalle_calculo_calculo 
            ON app.detalle_calculo_saldo(calculo_id)
        """)
        
        conn.commit()
        cur.close()
        conn.close()
        
        print('✅ Tablas de cálculo de saldo insoluto creadas exitosamente')
        print('✅ Índices optimizados creados')
        return True
        
    except Exception as e:
        print(f'❌ Error creando tablas de cálculo: {e}')
        if conn:
            conn.rollback()
            conn.close()
        return False

def add_firma_funcionario_columns():
    """Agregar columnas de firma de funcionario a la tabla solicitudes"""
    conn = get_db_connection()
    if not conn:
        print("❌ No se pudo conectar a la base de datos")
        return False
    
    try:
        cur = conn.cursor()
        
        # Agregar columna firmado_funcionario
        cur.execute("""
            ALTER TABLE app.solicitudes 
            ADD COLUMN IF NOT EXISTS firmado_funcionario BOOLEAN DEFAULT FALSE
        """)
        
        # Agregar columna fecha_firma_funcionario
        cur.execute("""
            ALTER TABLE app.solicitudes 
            ADD COLUMN IF NOT EXISTS fecha_firma_funcionario TIMESTAMP
        """)
        
        # Agregar columna funcionario_id_firma con referencia a funcionarios
        cur.execute("""
            ALTER TABLE app.solicitudes 
            ADD COLUMN IF NOT EXISTS funcionario_id_firma INTEGER REFERENCES app.funcionarios(id) ON DELETE SET NULL
        """)
        
        # Crear índice para optimizar consultas de firmas
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_solicitudes_firmado_funcionario 
            ON app.solicitudes(firmado_funcionario)
        """)
        
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_solicitudes_funcionario_firma 
            ON app.solicitudes(funcionario_id_firma)
        """)
        
        conn.commit()
        cur.close()
        conn.close()
        
        print('✅ Columnas de firma de funcionario agregadas a app.solicitudes')
        print('✅ Índices optimizados creados')
        return True
        
    except Exception as e:
        print(f'❌ Error agregando columnas de firma: {e}')
        if conn:
            conn.rollback()
            conn.close()
        return False

def fix_rut_columns():
    """Aumentar el tamaño de las columnas de RUT de VARCHAR(12) a VARCHAR(20)"""
    conn = get_db_connection()
    if not conn:
        print("❌ No se pudo conectar a la base de datos")
        return False
    
    try:
        cur = conn.cursor()
        
        # Lista de tablas y columnas que pueden tener RUT con tamaño insuficiente
        alter_statements = [
            # Tabla causante
            "ALTER TABLE app.causante ALTER COLUMN fal_run TYPE VARCHAR(20)",
            # Tabla representante
            "ALTER TABLE app.representante ALTER COLUMN rep_rut TYPE VARCHAR(20)",
            # Tabla solicitudes (campos que almacenan RUTs)
            "ALTER TABLE app.solicitudes ALTER COLUMN representante_rut TYPE VARCHAR(20)",
            "ALTER TABLE app.solicitudes ALTER COLUMN causante_rut TYPE VARCHAR(20)",
            # Tabla beneficiarios
            "ALTER TABLE app.beneficiarios ALTER COLUMN ben_run TYPE VARCHAR(20)",
        ]
        
        for statement in alter_statements:
            try:
                cur.execute(statement)
                print(f'✅ Columnas de RUT actualizadas: {statement.split("COLUMN")[1].strip()}')
            except Exception as e:
                # Si la columna ya tiene el tamaño correcto o no existe, continuar
                error_msg = str(e)
                if 'does not exist' not in error_msg.lower() and 'already' not in error_msg.lower():
                    print(f'⚠️  {statement.split("COLUMN")[1].strip()}: {error_msg}')
        
        conn.commit()
        cur.close()
        conn.close()
        
        print('✅ Columnas de RUT actualizadas exitosamente')
        return True
        
    except Exception as e:
        print(f'❌ Error actualizando columnas de RUT: {e}')
        if conn:
            conn.rollback()
            conn.close()
        return False

def remove_unused_firma_columns():
    """Eliminar columnas fecha_firma_funcionario y funcionario_id_firma de app.solicitudes"""
    conn = get_db_connection()
    if not conn:
        print("❌ No se pudo conectar a la base de datos")
        return False
    
    try:
        cur = conn.cursor()
        
        # Eliminar columna fecha_firma_funcionario si existe
        try:
            cur.execute("ALTER TABLE app.solicitudes DROP COLUMN IF EXISTS fecha_firma_funcionario")
            print('✅ Columna fecha_firma_funcionario eliminada')
        except Exception as e:
            print(f'⚠️ Error eliminando fecha_firma_funcionario: {e}')
        
        # Eliminar columna funcionario_id_firma si existe
        try:
            cur.execute("ALTER TABLE app.solicitudes DROP COLUMN IF EXISTS funcionario_id_firma")
            print('✅ Columna funcionario_id_firma eliminada')
        except Exception as e:
            print(f'⚠️ Error eliminando funcionario_id_firma: {e}')
        
        conn.commit()
        cur.close()
        conn.close()
        
        print('✅ Columnas innecesarias eliminadas exitosamente')
        return True
        
    except Exception as e:
        print(f'❌ Error eliminando columnas: {e}')
        if conn:
            conn.rollback()
            conn.close()
        return False

def create_aprobacion_items_table():
    """Crear tabla para almacenar aprobaciones/rechazos de items individuales por jefatura"""
    conn = get_db_connection()
    if not conn:
        print("❌ No se pudo conectar a la base de datos")
        return False
    
    try:
        cur = conn.cursor()
        
        # Crear tabla aprobacion_items
        cur.execute("""
            CREATE TABLE IF NOT EXISTS app.aprobacion_items (
                id SERIAL PRIMARY KEY,
                expediente_id INTEGER NOT NULL REFERENCES app.expediente(id) ON DELETE CASCADE,
                solicitud_id INTEGER NOT NULL REFERENCES app.solicitudes(id) ON DELETE CASCADE,
                item_tipo VARCHAR(50) NOT NULL,
                item_id INTEGER,
                estado VARCHAR(20) NOT NULL DEFAULT 'pendiente',
                observacion TEXT,
                aprobado_por INTEGER REFERENCES app.funcionarios(id) ON DELETE SET NULL,
                fecha_aprobacion TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                CONSTRAINT chk_estado CHECK (estado IN ('pendiente', 'aprobado', 'rechazado')),
                CONSTRAINT chk_item_tipo CHECK (item_tipo IN ('causante', 'beneficiarios', 'firmas', 'calculo', 'documentos', 'general'))
            )
        """)
        
        # Crear índices para optimizar consultas
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_aprobacion_items_expediente 
            ON app.aprobacion_items(expediente_id)
        """)
        
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_aprobacion_items_solicitud 
            ON app.aprobacion_items(solicitud_id)
        """)
        
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_aprobacion_items_tipo 
            ON app.aprobacion_items(item_tipo)
        """)
        
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_aprobacion_items_estado 
            ON app.aprobacion_items(estado)
        """)
        
        # Índice único para evitar duplicados (un item solo puede tener un registro activo)
        cur.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS idx_aprobacion_items_unique 
            ON app.aprobacion_items(expediente_id, solicitud_id, item_tipo)
        """)
        
        conn.commit()
        cur.close()
        conn.close()
        
        print('✅ Tabla aprobacion_items creada exitosamente')
        print('✅ Índices optimizados creados')
        return True
        
    except Exception as e:
        print(f'❌ Error creando tabla aprobacion_items: {e}')
        if conn:
            conn.rollback()
            conn.close()
        return False


