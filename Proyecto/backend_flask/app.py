from flask import Flask, request, jsonify, send_file, session, redirect, url_for, render_template_string
from flask_cors import CORS
from flask_session import Session
import psycopg2
from psycopg2.extras import RealDictCursor
import os
from datetime import datetime
import json
import time
import hashlib
import hmac
import secrets
import io
import zipfile
import bcrypt
from werkzeug.utils import secure_filename
from config import Config
from functools import wraps
from docxtpl import DocxTemplate
from utils.helpers import formatear_rut, formatear_fecha, formatear_moneda
from xhtml2pdf import pisa

# Importar pywintypes para asegurar que esté disponible para docx2pdf
try:
    import pywintypes
    print('✅ pywintypes importado correctamente')
except ImportError:
    print('⚠️ pywintypes no disponible - la conversión a PDF puede fallar')

app = Flask(__name__)
CORS(app, supports_credentials=True, origins=[
    'http://localhost:8000',
    'http://localhost:8080',
    'http://127.0.0.1:8000',
    'http://127.0.0.1:8080'
])

# Configuración de sesiones
app.config['SECRET_KEY'] = 'tu_clave_secreta_muy_segura_aqui'
app.config['SESSION_TYPE'] = 'filesystem'
app.config['SESSION_PERMANENT'] = False
app.config['SESSION_USE_SIGNER'] = True
app.config['SESSION_KEY_PREFIX'] = 'saldo_insoluto:'
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['SESSION_COOKIE_SECURE'] = False  # Para desarrollo local

# Inicializar Flask-Session
Session(app)

# Función helper para verificar si una solicitud está lista para evaluación (todas las firmas + cálculo completo)
def verificar_y_actualizar_estado_pendiente(expediente_id, solicitud_id, cur, conn):
    """Verificar si todas las firmas y el cálculo están completos, y actualizar estado a 'pendiente'"""
    try:
        print(f"🔍 Verificando si solicitud {solicitud_id} puede cambiar a 'pendiente'...")
        
        # 1. Verificar que el funcionario haya firmado
        cur.execute("""
            SELECT firmado_funcionario, estado 
            FROM app.solicitudes 
            WHERE id = %s
        """, (solicitud_id,))
        solicitud = cur.fetchone()
        
        if not solicitud:
            print(f"❌ Solicitud {solicitud_id} no encontrada")
            return False
        
        estado_actual = solicitud[1]
        firmado_funcionario = solicitud[0]
        
        print(f"📊 Estado actual: '{estado_actual}', Funcionario firmado: {firmado_funcionario}")
        
        if not firmado_funcionario:
            print(f"⏳ Solicitud {solicitud_id}: Funcionario aún no ha firmado")
            return False
        
        # 2. Verificar que todos los beneficiarios hayan firmado
        cur.execute("""
            SELECT 
                COUNT(b.id) as total_beneficiarios,
                COUNT(uf.id) as beneficiarios_firmados
            FROM app.beneficiarios b
            LEFT JOIN app.usuarios_firma uf ON b.ben_run = uf.rut
            WHERE b.expediente_id = %s
        """, (expediente_id,))
        
        firmas_result = cur.fetchone()
        total_beneficiarios = firmas_result[0] or 0
        beneficiarios_firmados = firmas_result[1] or 0
        
        print(f"📝 Beneficiarios: {beneficiarios_firmados}/{total_beneficiarios} firmados")
        
        if total_beneficiarios > 0 and beneficiarios_firmados < total_beneficiarios:
            print(f"⏳ Solicitud {solicitud_id}: Faltan firmas de beneficiarios ({beneficiarios_firmados}/{total_beneficiarios})")
            return False
        
        # 3. Verificar que el cálculo de saldo insoluto esté completo
        # Buscar el cálculo más reciente (puede estar en la misma transacción)
        cur.execute("""
            SELECT id, estado, fecha_calculo
            FROM app.calculo_saldo_insoluto 
            WHERE expediente_id = %s AND estado IN ('pendiente', 'aprobado')
            ORDER BY fecha_calculo DESC, id DESC LIMIT 1
        """, (expediente_id,))
        
        calculo = cur.fetchone()
        if not calculo:
            # Si no se encuentra, buscar cualquier cálculo del expediente para diagnóstico
            cur.execute("""
                SELECT id, estado, fecha_calculo
                FROM app.calculo_saldo_insoluto 
                WHERE expediente_id = %s
                ORDER BY fecha_calculo DESC, id DESC LIMIT 1
            """, (expediente_id,))
            calculo_alternativo = cur.fetchone()
            if calculo_alternativo:
                print(f"⚠️ Solicitud {solicitud_id}: Cálculo encontrado pero con estado incorrecto")
                print(f"   Cálculo ID: {calculo_alternativo[0]}, Estado: '{calculo_alternativo[1]}'")
                print(f"   Se requiere estado 'pendiente' o 'aprobado'")
            else:
                print(f"⏳ Solicitud {solicitud_id}: No se encontró ningún cálculo de saldo insoluto para este expediente")
            return False
        
        print(f"💰 Cálculo encontrado: ID {calculo[0]}, Estado: '{calculo[1]}', Fecha: {calculo[2]}")
        
        # 4. Si todas las condiciones se cumplen, actualizar estado a 'pendiente'
        # Permitir cambiar desde 'borrador' o 'firmado_funcionario' a 'pendiente'
        # Solo excluir estados finales: 'pendiente' (ya está), 'completado' (aprobado)
        cur.execute("""
            UPDATE app.solicitudes 
            SET estado = 'pendiente'
            WHERE id = %s AND estado NOT IN ('pendiente', 'completado')
        """, (solicitud_id,))
        
        if cur.rowcount > 0:
            print(f"✅ Solicitud {solicitud_id} actualizada de '{estado_actual}' a 'pendiente' - Todas las firmas y cálculo completos")
            return True
        else:
            print(f"ℹ️ Solicitud {solicitud_id} no se actualizó. Estado actual: '{estado_actual}' (puede estar en estado final)")
            return False
            
    except Exception as e:
        print(f"⚠️ Error verificando estado pendiente: {e}")
        import traceback
        print(traceback.format_exc())
        return False

# Decorador para requerir autenticación
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        print(f"🔍 Verificando sesión para {f.__name__}")
        print(f"🔍 Session keys: {list(session.keys())}")
        print(f"🔍 User ID en sesión: {session.get('user_id', 'NO HAY')}")
        
        if 'user_id' not in session:
            print(f"❌ No autorizado - no hay user_id en sesión")
            return jsonify({'error': 'No autorizado', 'redirect': '/IngresoCredenciales.html'}), 401
        
        print(f"✅ Autorizado - user_id: {session['user_id']}")
        return f(*args, **kwargs)
    return decorated_function

# Configuración de la aplicación
app.config.from_object(Config)

# CORS ya configurado arriba

# Configuración de la base de datos
DB_CONFIG = Config().DATABASE_CONFIG

# Configuración para archivos
ALLOWED_EXTENSIONS = {'pdf', 'png', 'jpg', 'jpeg', 'gif', 'doc', 'docx', 'xls', 'xlsx'}
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB máximo

def get_db_connection():
    """Obtener conexión a la base de datos"""
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        return conn
    except Exception as e:
        print(f"❌ Error conectando a PostgreSQL: {e}")
        return None

def create_firmas_beneficiarios_table():
    """Crear tabla para almacenar firmas de beneficiarios"""
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

def allowed_file(filename):
    """Verificar si el archivo tiene una extensión permitida"""
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def get_file_hash(file_data):
    """Generar hash SHA256 del archivo"""
    return hashlib.sha256(file_data).hexdigest()

def get_mime_type(filename):
    """Obtener tipo MIME basado en la extensión del archivo"""
    mime_types = {
        'pdf': 'application/pdf',
        'png': 'image/png',
        'jpg': 'image/jpeg',
        'jpeg': 'image/jpeg',
        'gif': 'image/gif',
        'doc': 'application/msword',
        'docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        'xls': 'application/vnd.ms-excel',
        'xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    }
    ext = filename.rsplit('.', 1)[1].lower()
    return mime_types.get(ext, 'application/octet-stream')

def validar_rut_chileno(rut):
    """Validar RUT chileno con algoritmo de dígito verificador"""
    try:
        print(f"🔍 Validando RUT: '{rut}'")
        
        # Limpiar RUT
        rut_limpio = rut.replace('.', '').replace('-', '').upper()
        print(f"🔍 RUT limpio: '{rut_limpio}'")
        
        if len(rut_limpio) < 8 or len(rut_limpio) > 9:
            print(f"❌ RUT muy corto/largo: {len(rut_limpio)} caracteres")
            return False
        
        # Separar número y dígito verificador
        numero = rut_limpio[:-1]
        dv = rut_limpio[-1]
        print(f"🔍 Número: '{numero}', DV: '{dv}'")
        
        # Validar que el número sea solo dígitos
        if not numero.isdigit():
            return False
        
        # Calcular dígito verificador
        suma = 0
        multiplicador = 2
        
        for digito in reversed(numero):
            suma += int(digito) * multiplicador
            multiplicador = multiplicador + 1 if multiplicador < 7 else 2
        
        resto = suma % 11
        dv_calculado = 11 - resto
        
        if dv_calculado == 11:
            dv_calculado = '0'
        elif dv_calculado == 10:
            dv_calculado = 'K'
        else:
            dv_calculado = str(dv_calculado)
        
        print(f"🔍 DV ingresado: '{dv}', DV calculado: '{dv_calculado}'")
        resultado = dv == dv_calculado
        print(f"🔍 Resultado validación: {resultado}")
        
        return resultado
        
    except Exception:
        return False

def hash_password(password):
    """Encriptar contraseña con bcrypt"""
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')

@app.route('/api/solicitudes', methods=['POST'])
@login_required
def crear_solicitud():
    """Crear una nueva solicitud de saldo insoluto"""
    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Error de conexión a la base de datos'}), 500
    
    try:
        cur = conn.cursor()
        
        # Iniciar transacción
        cur.execute('BEGIN')
        
        # 1. Crear expediente principal
        expediente_numero = f"EXP-{datetime.now().year}-{datetime.now().strftime('%H%M%S')}"
        # Obtener funcionario_id de la sesión
        funcionario_id = session.get('user_id', 1)  # Usar ID del usuario logueado
        
        cur.execute("""
            INSERT INTO app.expediente (expediente_numero, estado, observaciones, funcionario_id)
            VALUES (%s, 'en_proceso', 'Expediente de saldo insoluto creado automáticamente', %s)
            RETURNING id
        """, (expediente_numero, funcionario_id))
        expediente_id = cur.fetchone()[0]
        
        # Datos del formulario
        data = request.get_json()
        
        # Debug: Mostrar los datos recibidos
        print('🔍 Datos recibidos del frontend:')
        print(f'  fal_fecha_defuncion: {data.get("fal_fecha_defuncion", "")}')
        print(f'  fal_comuna_defuncion: {data.get("fal_comuna_defuncion", "")}')
        print(f'  fal_nombre: {data.get("fal_nombre", "")}')
        print(f'  fal_run: {data.get("fal_run", "")}')
        
        # 2. Crear o actualizar representante en tabla específica
        cur.execute("""
            INSERT INTO app.representante (expediente_id, rep_rut, rep_calidad, rep_nombre, rep_apellido_p, rep_apellido_m, rep_telefono, rep_direccion, rep_comuna, rep_region, rep_email)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (rep_rut) DO UPDATE SET
                expediente_id = EXCLUDED.expediente_id,
                rep_calidad = EXCLUDED.rep_calidad,
                rep_nombre = EXCLUDED.rep_nombre,
                rep_apellido_p = EXCLUDED.rep_apellido_p,
                rep_apellido_m = EXCLUDED.rep_apellido_m,
                rep_telefono = EXCLUDED.rep_telefono,
                rep_direccion = EXCLUDED.rep_direccion,
                rep_comuna = EXCLUDED.rep_comuna,
                rep_region = EXCLUDED.rep_region,
                rep_email = EXCLUDED.rep_email,
                actualizado_en = NOW()
            RETURNING rep_rut
        """, (
            expediente_id,
            data.get('rep_run') or None,
            data.get('rep_calidad') or None,
            data.get('rep_nombre') or None,
            data.get('rep_apellido_p') or None,
            data.get('rep_apellido_m') or None,
            data.get('rep_telefono') or None,
            data.get('rep_direccion') or None,
            data.get('rep_comuna') or None,
            data.get('rep_region') or None,
            data.get('rep_email') or None
        ))
        representante_rut = cur.fetchone()[0]
        
        # 3. Crear o actualizar causante en tabla específica
        cur.execute("""
            INSERT INTO app.causante (expediente_id, fal_run, fal_nacionalidad, fal_nombre, fal_apellido_p, fal_apellido_m, fal_fecha_defuncion, fal_comuna_defuncion, motivo_solicitud)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (fal_run) DO UPDATE SET
                expediente_id = EXCLUDED.expediente_id,
                fal_nacionalidad = EXCLUDED.fal_nacionalidad,
                fal_nombre = EXCLUDED.fal_nombre,
                fal_apellido_p = EXCLUDED.fal_apellido_p,
                fal_apellido_m = EXCLUDED.fal_apellido_m,
                fal_fecha_defuncion = EXCLUDED.fal_fecha_defuncion,
                fal_comuna_defuncion = EXCLUDED.fal_comuna_defuncion,
                motivo_solicitud = EXCLUDED.motivo_solicitud,
                actualizado_en = NOW()
            RETURNING fal_run
        """, (
            expediente_id,
            data.get('fal_run') or None,
            data.get('fal_nacionalidad') or None,
            data.get('fal_nombre') or None,
            data.get('fal_apellido_p') or None,
            data.get('fal_apellido_m') or None,
            data.get('fal_fecha_defuncion') or None,
            data.get('fal_comuna_defuncion') or None,
            data.get('motivo_solicitud') or None
        ))
        causante_run = cur.fetchone()[0]
        
        # 4. Crear solicitud con folio secuencial
        # Obtener el próximo número secuencial para el año actual
        año_actual = datetime.now().year
        
        # Consulta más simple y robusta
        cur.execute("""
            SELECT COALESCE(MAX(
                CASE 
                    WHEN folio ~ ('^SI-\\d{3}-' || %s) THEN 
                        CAST(SUBSTRING(folio FROM 'SI-(\\d{3})-') AS INTEGER)
                    ELSE 0
                END
            ), 0) + 1
            FROM app.solicitudes 
            WHERE folio LIKE ('SI-%%-' || %s)
        """, (año_actual, año_actual))
        
        numero_secuencial = cur.fetchone()[0]
        folio = f"SI-{numero_secuencial:03d}-{año_actual}"
        
        print(f'🔢 Generando folio: {folio} (número secuencial: {numero_secuencial})')
        cur.execute("""
            INSERT INTO app.solicitudes (expediente_id, folio, estado, sucursal, observacion, representante_rut, causante_rut, fecha_defuncion, comuna_fallecimiento)
            VALUES (%s, %s, 'borrador', %s, %s, %s, %s, %s, %s)
            RETURNING id
        """, (
            expediente_id, folio, data.get('sucursal') or None, data.get('motivo_solicitud') or None,
            representante_rut, causante_run, data.get('fal_fecha_defuncion') or None, data.get('fal_comuna_defuncion') or None
        ))
        solicitud_id = cur.fetchone()[0]
        
        print(f'📋 Solicitud creada - ID: {solicitud_id}, Folio: {folio}')
        
        # 5. Crear beneficiarios en tabla específica
        beneficiarios = data.get('beneficiarios', [])
        if beneficiarios and isinstance(beneficiarios, list):
            for beneficiario in beneficiarios:
                if beneficiario.get('nombre') and beneficiario.get('run'):
                    cur.execute("""
                        INSERT INTO app.beneficiarios (expediente_id, solicitud_id, ben_nombre, ben_run, ben_parentesco, es_representante)
                        VALUES (%s, %s, %s, %s, %s, %s)
                        RETURNING id
                    """, (
                        expediente_id, solicitud_id, beneficiario.get('nombre'),
                        beneficiario.get('run'), beneficiario.get('parentesco') or None,
                        beneficiario.get('es_representante', False)
                    ))
        
        # 6. Crear documentos (simplificado)
        tipo_documento = data.get('tipo_documento')
        if tipo_documento:
            cur.execute("""
                INSERT INTO app.documentos_saldo_insoluto (expediente_id, solicitud_id, doc_tipo_id, doc_nombre_archivo, doc_estado)
                VALUES (%s, %s, %s, %s, 'pendiente')
                RETURNING id
            """, (expediente_id, solicitud_id, 1, f"documento_{solicitud_id}"))
        
        # 7. Crear validación (solo requiere firma del funcionario)
        cur.execute("""
            INSERT INTO app.validacion (expediente_id, solicitud_id, val_sucursal, val_estado)
            VALUES (%s, %s, %s, 'pendiente')
            RETURNING id
        """, (expediente_id, solicitud_id, data.get('sucursal') or None))
        
        # Confirmar transacción
        cur.execute('COMMIT')
        
        # Respuesta exitosa
        response = {
            'success': True,
            'message': 'Solicitud creada exitosamente',
            'data': {
                'expediente_id': expediente_id,
                'expediente_numero': expediente_numero,
                'solicitud_id': solicitud_id,
                'folio': folio,
                'estado': 'borrador'
            }
        }
        
        print(f'📤 Enviando respuesta: {response}')
        
        cur.close()
        conn.close()
        return jsonify(response), 201
        
    except Exception as e:
        # Rollback en caso de error
        cur.execute('ROLLBACK')
        print(f'❌ Error creando solicitud: {e}')
        cur.close()
        conn.close()
        return jsonify({'error': f'Error interno del servidor: {str(e)}'}), 500

@app.route('/api/solicitudes/<int:solicitud_id>/firma-representante', methods=['POST'])
def firmar_representante(solicitud_id):
    """Firmar como representante"""
    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Error de conexión a la base de datos'}), 500
    
    try:
        cur = conn.cursor()
        data = request.get_json()
        
        # Crear firma HMAC-SHA256
        payload = json.dumps(data.get('payload', {}), sort_keys=True)
        clave = data.get('clave', '')
        salt = data.get('salt', '')
        
        # Generar firma
        firma_data = {
            'firma': hmac.new(
                clave.encode('utf-8'),
                (payload + salt).encode('utf-8'),
                hashlib.sha256
            ).hexdigest(),
            'timestamp': datetime.now().isoformat(),
            'solicitud_id': solicitud_id
        }
        
        # Actualizar validación
        cur.execute("""
            UPDATE app.validacion 
            SET val_firma_representante = %s
            WHERE solicitud_id = %s
        """, (json.dumps(firma_data), solicitud_id))
        
        conn.commit()
        cur.close()
        conn.close()
        
        return jsonify({'success': True, 'message': 'Firma de representante guardada'}), 200
        
    except Exception as e:
        print(f'❌ Error firmando representante: {e}')
        cur.close()
        conn.close()
        return jsonify({'error': f'Error interno del servidor: {str(e)}'}), 500

@app.route('/api/solicitudes/<int:solicitud_id>/firma-funcionario', methods=['POST'])
def firmar_funcionario(solicitud_id):
    """Firmar como funcionario"""
    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Error de conexión a la base de datos'}), 500
    
    try:
        cur = conn.cursor()
        data = request.get_json()
        
        # Crear firma HMAC-SHA256
        payload = json.dumps(data.get('payload', {}), sort_keys=True)
        clave = data.get('clave', '')
        salt = data.get('salt', '')
        
        # Generar firma
        firma_data = {
            'firma': hmac.new(
                clave.encode('utf-8'),
                (payload + salt).encode('utf-8'),
                hashlib.sha256
            ).hexdigest(),
            'timestamp': datetime.now().isoformat(),
            'solicitud_id': solicitud_id
        }
        
        # Actualizar validación
        cur.execute("""
            UPDATE app.validacion 
            SET val_firma_funcionario = %s
            WHERE solicitud_id = %s
        """, (json.dumps(firma_data), solicitud_id))
        
        conn.commit()
        cur.close()
        conn.close()
        
        return jsonify({'success': True, 'message': 'Firma de funcionario guardada'}), 200
        
    except Exception as e:
        print(f'❌ Error firmando funcionario: {e}')
        cur.close()
        conn.close()
        return jsonify({'error': f'Error interno del servidor: {str(e)}'}), 500

@app.route('/api/expediente/<int:expediente_id>', methods=['GET'])
def obtener_expediente(expediente_id):
    """Obtener un expediente completo con todos sus datos"""
    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Error de conexión a la base de datos'}), 500
    
    try:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        # Obtener expediente
        cur.execute("SELECT * FROM app.expediente WHERE id = %s", (expediente_id,))
        expediente = cur.fetchone()
        
        if not expediente:
            return jsonify({'error': 'Expediente no encontrado'}), 404
        
        # Obtener representante
        cur.execute("SELECT * FROM app.representante WHERE expediente_id = %s", (expediente_id,))
        representante = cur.fetchone()
        
        # Obtener causante
        cur.execute("SELECT * FROM app.causante WHERE expediente_id = %s", (expediente_id,))
        causante = cur.fetchone()
        
        # Obtener solicitudes
        cur.execute("SELECT * FROM app.solicitudes WHERE expediente_id = %s", (expediente_id,))
        solicitudes = cur.fetchall()
        
        # Obtener beneficiarios
        cur.execute("SELECT * FROM app.beneficiarios WHERE expediente_id = %s", (expediente_id,))
        beneficiarios = cur.fetchall()
        
        # Obtener documentos
        cur.execute("SELECT * FROM app.documentos_saldo_insoluto WHERE expediente_id = %s", (expediente_id,))
        documentos = cur.fetchall()
        
        # Obtener validación
        cur.execute("SELECT * FROM app.validacion WHERE expediente_id = %s", (expediente_id,))
        validacion = cur.fetchone()
        
        # Construir respuesta
        response = {
            'expediente': dict(expediente) if expediente else None,
            'representante': dict(representante) if representante else None,
            'causante': dict(causante) if causante else None,
            'solicitudes': [dict(s) for s in solicitudes],
            'beneficiarios': [dict(b) for b in beneficiarios],
            'documentos': [dict(d) for d in documentos],
            'validacion': dict(validacion) if validacion else None
        }
        
        cur.close()
        conn.close()
        return jsonify(response), 200
        
    except Exception as e:
        print(f'❌ Error obteniendo expediente: {e}')
        cur.close()
        conn.close()
        return jsonify({'error': f'Error interno del servidor: {str(e)}'}), 500

@app.route('/api/upload-documento', methods=['POST'])
@login_required
def upload_documento():
    """Subir un documento como BLOB"""
    print('📁 Iniciando subida de archivo...')
    print(f'📋 Form data recibido: {dict(request.form)}')
    print(f'📋 Files recibidos: {list(request.files.keys())}')
    
    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Error de conexión a la base de datos'}), 500
    
    try:
        # Verificar que se envió un archivo
        if 'archivo' not in request.files:
            print('❌ No se encontró archivo en la petición')
            return jsonify({'error': 'No se encontró archivo en la petición'}), 400
        
        file = request.files['archivo']
        print(f'📄 Archivo recibido: {file.filename}')
        
        if file.filename == '':
            print('❌ No se seleccionó ningún archivo')
            return jsonify({'error': 'No se seleccionó ningún archivo'}), 400
        
        # Verificar extensión permitida
        if not allowed_file(file.filename):
            print(f'❌ Extensión no permitida: {file.filename}')
            return jsonify({
                'error': f'Extensión no permitida. Extensiones válidas: {", ".join(ALLOWED_EXTENSIONS)}'
            }), 400
        
        # Leer el archivo
        file_data = file.read()
        
        # Verificar tamaño
        if len(file_data) > MAX_FILE_SIZE:
            return jsonify({
                'error': f'Archivo demasiado grande. Tamaño máximo: {MAX_FILE_SIZE // (1024*1024)}MB'
            }), 400
        
        # Obtener datos adicionales
        solicitud_id = request.form.get('solicitud_id')
        doc_tipo_id = request.form.get('doc_tipo_id', 1)
        observaciones = request.form.get('observaciones', '')
        
        print(f'🆔 Solicitud ID recibido: "{solicitud_id}" (tipo: {type(solicitud_id)})')
        
        if not solicitud_id or solicitud_id == 'undefined':
            print('❌ ID de solicitud requerido')
            return jsonify({'error': 'ID de solicitud requerido'}), 400
        
        # Validar que solicitud_id sea un número
        try:
            solicitud_id = int(solicitud_id)
            print(f'✅ Solicitud ID convertido a entero: {solicitud_id}')
        except (ValueError, TypeError):
            print(f'❌ Error convirtiendo solicitud_id a entero: {solicitud_id}')
            return jsonify({'error': 'ID de solicitud debe ser un número válido'}), 400
        
        # Generar hash del archivo
        file_hash = get_file_hash(file_data)
        
        # Obtener tipo MIME
        mime_type = get_mime_type(file.filename)
        
        # Nombre seguro del archivo
        safe_filename = secure_filename(file.filename)
        
        cur = conn.cursor()
        
        # Verificar si ya existe un archivo con el mismo hash (DESHABILITADO TEMPORALMENTE)
        # cur.execute("""
        #     SELECT id FROM app.documentos_saldo_insoluto 
        #     WHERE doc_sha256 = %s
        # """, (file_hash,))
        
        # existing_doc = cur.fetchone()
        # if existing_doc:
        #     return jsonify({
        #         'error': 'Ya existe un archivo idéntico en el sistema',
        #         'documento_id': existing_doc[0]
        #     }), 409
        
        # Obtener expediente_id de la solicitud
        cur.execute("""
            SELECT expediente_id FROM app.solicitudes WHERE id = %s
        """, (solicitud_id,))
        
        expediente_result = cur.fetchone()
        if not expediente_result:
            return jsonify({'error': 'Solicitud no encontrada'}), 404
        
        expediente_id = expediente_result[0]
        
        # Insertar el documento
        cur.execute("""
            INSERT INTO app.documentos_saldo_insoluto 
            (expediente_id, solicitud_id, doc_tipo_id, doc_nombre_archivo, doc_archivo_blob, 
             doc_mime_type, doc_tamano_bytes, doc_sha256, doc_ruta_storage, doc_observaciones, 
             doc_estado, doc_fecha_subida)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'subido', NOW())
            RETURNING id
        """, (
            expediente_id, solicitud_id, doc_tipo_id, safe_filename, file_data,
            mime_type, len(file_data), file_hash, "/api/download-documento/temp", observaciones
        ))
        
        documento_id = cur.fetchone()[0]
        
        # Actualizar la ruta con el ID real del documento
        cur.execute("""
            UPDATE app.documentos_saldo_insoluto 
            SET doc_ruta_storage = %s
            WHERE id = %s
        """, (f"/api/download-documento/{documento_id}", documento_id))
        
        conn.commit()
        cur.close()
        conn.close()
        
        print(f'📁 Archivo subido: {safe_filename} ({len(file_data)} bytes)')
        print(f'🔗 Ruta generada: /api/download-documento/{documento_id}')
        
        return jsonify({
            'success': True,
            'message': 'Archivo subido exitosamente',
            'data': {
                'documento_id': documento_id,
                'expediente_id': expediente_id,
                'nombre_archivo': safe_filename,
                'tamano_bytes': len(file_data),
                'mime_type': mime_type,
                'sha256_hash': file_hash,
                'ruta_storage': f"/api/download-documento/{documento_id}"
            }
        }), 201
        
    except Exception as e:
        print(f'❌ Error subiendo archivo: {e}')
        if 'conn' in locals():
            conn.rollback()
            conn.close()
        return jsonify({'error': f'Error interno del servidor: {str(e)}'}), 500

@app.route('/api/download-documento/<int:documento_id>', methods=['GET'])
def download_documento(documento_id):
    """Descargar un documento por ID"""
    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Error de conexión a la base de datos'}), 500
    
    try:
        cur = conn.cursor()
        
        # Obtener el documento
        cur.execute("""
            SELECT doc_nombre_archivo, doc_archivo_blob, doc_mime_type, doc_tamano_bytes
            FROM app.documentos_saldo_insoluto 
            WHERE id = %s
        """, (documento_id,))
        
        documento = cur.fetchone()
        if not documento:
            return jsonify({'error': 'Documento no encontrado'}), 404
        
        nombre_archivo, archivo_blob, mime_type, tamano_bytes = documento
        
        cur.close()
        conn.close()
        
        # Crear objeto BytesIO para enviar el archivo
        file_obj = io.BytesIO(archivo_blob)
        
        print(f'📥 Descargando archivo: {nombre_archivo} ({tamano_bytes} bytes)')
        
        return send_file(
            file_obj,
            mimetype=mime_type,
            as_attachment=True,
            download_name=nombre_archivo
        )
        
    except Exception as e:
        print(f'❌ Error descargando archivo: {e}')
        if 'conn' in locals():
            conn.close()
        return jsonify({'error': f'Error interno del servidor: {str(e)}'}), 500

@app.route('/api/documentos/<int:documento_id>/ver', methods=['GET'])
@login_required
def ver_documento(documento_id):
    """Visualizar un documento por ID (sin descarga)"""
    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Error de conexión a la base de datos'}), 500
    
    try:
        cur = conn.cursor()
        
        # Obtener el documento
        cur.execute("""
            SELECT doc_nombre_archivo, doc_archivo_blob, doc_mime_type, doc_tamano_bytes
            FROM app.documentos_saldo_insoluto 
            WHERE id = %s
        """, (documento_id,))
        
        documento = cur.fetchone()
        if not documento:
            return jsonify({'error': 'Documento no encontrado'}), 404
        
        nombre_archivo, archivo_blob, mime_type, tamano_bytes = documento
        
        cur.close()
        conn.close()
        
        # Crear objeto BytesIO para enviar el archivo
        file_obj = io.BytesIO(archivo_blob)
        
        print(f'👁️ Visualizando archivo: {nombre_archivo} ({tamano_bytes} bytes)')
        
        # Enviar con as_attachment=False para visualización en navegador
        return send_file(
            file_obj,
            mimetype=mime_type,
            as_attachment=False,
            download_name=nombre_archivo
        )
        
    except Exception as e:
        print(f'❌ Error visualizando archivo: {e}')
        if 'conn' in locals():
            conn.close()
        return jsonify({'error': f'Error interno del servidor: {str(e)}'}), 500

@app.route('/api/documentos/<int:solicitud_id>', methods=['GET'])
def listar_documentos(solicitud_id):
    """Listar todos los documentos de una solicitud"""
    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Error de conexión a la base de datos'}), 500
    
    try:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        # Obtener documentos de la solicitud
        cur.execute("""
            SELECT id, doc_nombre_archivo, doc_mime_type, doc_tamano_bytes, 
                   doc_sha256_hash, doc_estado, doc_observaciones, doc_fecha_subida
            FROM app.documentos_saldo_insoluto 
            WHERE solicitud_id = %s
            ORDER BY doc_fecha_subida DESC
        """, (solicitud_id,))
        
        documentos = cur.fetchall()
        
        cur.close()
        conn.close()
        
        return jsonify({
            'success': True,
            'data': [dict(doc) for doc in documentos]
        }), 200
        
    except Exception as e:
        print(f'❌ Error listando documentos: {e}')
        if 'conn' in locals():
            conn.close()
        return jsonify({'error': f'Error interno del servidor: {str(e)}'}), 500

@app.route('/api/usuarios', methods=['POST'])
def crear_usuario():
    """Crear un nuevo usuario funcionario"""
    print("🔔 Petición recibida en /api/usuarios")
    print(f"📥 Datos recibidos: {request.get_json()}")
    
    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Error de conexión a la base de datos'}), 500
    
    try:
        data = request.get_json()
        
        # Validar datos requeridos
        required_fields = ['nombres', 'apellido_p', 'rut', 'email', 'rol', 'password', 'password_confirm']
        for field in required_fields:
            if not data.get(field):
                return jsonify({'error': f'Campo requerido: {field}'}), 400
        
        # Validar sucursal si se proporciona
        sucursal = data.get('sucursal', '').strip()
        if sucursal and sucursal not in ['providencia', 'nunoa', 'santo_domingo']:
            return jsonify({'error': 'Sucursal no válida'}), 400
        
        # Validar que las contraseñas coincidan
        if data['password'] != data['password_confirm']:
            return jsonify({'error': 'Las contraseñas no coinciden'}), 400
        
        # Validar RUT chileno
        print(f"🔍 RUT recibido: '{data['rut']}'")
        print(f"🔍 Tipo de RUT: {type(data['rut'])}")
        print(f"🔍 Longitud RUT: {len(data['rut'])}")
        
        if not validar_rut_chileno(data['rut']):
            print(f"❌ RUT inválido: '{data['rut']}'")
            return jsonify({'error': 'RUT inválido'}), 400
        else:
            print(f"✅ RUT válido: '{data['rut']}'")
        
        # Validar email
        import re
        email_pattern = r'^[^\s@]+@[^\s@]+\.[^\s@]+$'
        if not re.match(email_pattern, data['email']):
            return jsonify({'error': 'Formato de email inválido'}), 400
        
        # Validar rol
        valid_roles = ['ejecutivo_plataforma', 'jefatura']
        if data['rol'] not in valid_roles:
            return jsonify({'error': 'Rol inválido. Debe ser: ejecutivo_plataforma o jefatura'}), 400
        
        # Validar fortaleza de contraseña
        password = data['password']
        if len(password) < 8:
            return jsonify({'error': 'La contraseña debe tener al menos 8 caracteres'}), 400
        
        # Verificar requisitos de contraseña
        has_upper = any(c.isupper() for c in password)
        has_lower = any(c.islower() for c in password)
        has_digit = any(c.isdigit() for c in password)
        has_special = any(c in '!@#$%^&*()_+-=[]{}|;:,.<>?' for c in password)
        
        if not all([has_upper, has_lower, has_digit, has_special]):
            return jsonify({'error': 'La contraseña debe tener mayúsculas, minúsculas, números y símbolos'}), 400
        
        cur = conn.cursor()
        
        # Verificar si el RUT ya existe
        cur.execute("SELECT id FROM app.funcionarios WHERE rut = %s", (data['rut'],))
        if cur.fetchone():
            return jsonify({'error': 'Ya existe un funcionario con este RUT'}), 409
        
        # Verificar si el email ya existe
        cur.execute("SELECT id FROM app.funcionarios WHERE email = %s", (data['email'],))
        if cur.fetchone():
            return jsonify({'error': 'Ya existe un funcionario con este email'}), 409
        
        # Encriptar contraseña
        password_hash = hash_password(password)
        
        # Insertar usuario (las iniciales se generan automáticamente por el trigger)
        cur.execute("""
            INSERT INTO app.funcionarios (rut, nombres, apellido_p, apellido_m, email, password_hash, rol, sucursal)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id, iniciales
        """, (
            data['rut'],
            data['nombres'].strip(),
            data['apellido_p'].strip(),
            data.get('apellido_m', '').strip() or None,
            data['email'].strip().lower(),
            password_hash,
            data['rol'],  # Rol seleccionado desde el frontend
            sucursal if sucursal else 'IPS Central'  # Sucursal seleccionada o por defecto
        ))
        
        result = cur.fetchone()
        usuario_id, iniciales = result
        
        conn.commit()
        cur.close()
        conn.close()
        
        print(f'👤 Usuario creado: {data["nombres"]} {data["apellido_p"]} - Iniciales: {iniciales}')
        
        return jsonify({
            'success': True,
            'message': 'Usuario creado exitosamente',
            'data': {
                'id': usuario_id,
                'rut': data['rut'],
                'nombres': data['nombres'],
                'apellido_p': data['apellido_p'],
                'apellido_m': data.get('apellido_m'),
                'email': data['email'],
                'iniciales': iniciales,
                'rol': data['rol'],
                'sucursal': sucursal if sucursal else 'IPS Central'
            }
        }), 201
        
    except Exception as e:
        print(f'❌ Error creando usuario: {e}')
        if 'conn' in locals():
            conn.rollback()
            conn.close()
        return jsonify({'error': f'Error interno del servidor: {str(e)}'}), 500

@app.route('/api/health', methods=['GET'])
def health_check():
    """Endpoint de salud del servidor"""
    return jsonify({
        'status': 'OK',
        'message': 'Servidor Flask funcionando correctamente',
        'timestamp': datetime.now().isoformat()
    }), 200


@app.route('/api/beneficiarios/<int:beneficiario_id>/firma', methods=['POST'])
@login_required
def firmar_beneficiario(beneficiario_id):
    """Firmar como beneficiario usando contraseña de app externa"""
    print(f"🔔 Petición de firma de beneficiario ID: {beneficiario_id}")
    
    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Error de conexión a la base de datos'}), 500
    
    try:
        data = request.get_json()
        
        # Validar datos requeridos
        if not data.get('firma_hash'):
            return jsonify({'error': 'Firma (contraseña) es requerida'}), 400
        
        if not data.get('expediente_id'):
            return jsonify({'error': 'ID de expediente es requerido'}), 400
        
        firma_hash = data['firma_hash']
        expediente_id = data['expediente_id']
        
        cur = conn.cursor()
        
        # Verificar que el beneficiario existe y pertenece al expediente
        cur.execute("""
            SELECT id, ben_nombre, ben_run 
            FROM app.beneficiarios 
            WHERE id = %s AND expediente_id = %s
        """, (beneficiario_id, expediente_id))
        
        beneficiario = cur.fetchone()
        if not beneficiario:
            return jsonify({'error': 'Beneficiario no encontrado o no pertenece al expediente'}), 404
        
        # Verificar si ya tiene una firma activa en usuarios_firma
        cur.execute("""
            SELECT uf.id FROM app.usuarios_firma uf
            JOIN app.beneficiarios b ON uf.rut = b.ben_run
            WHERE b.id = %s AND b.expediente_id = %s
        """, (beneficiario_id, expediente_id))
        
        if cur.fetchone():
            return jsonify({'error': 'El beneficiario ya tiene una firma activa'}), 400
        
        # La firma ya existe en usuarios_firma, solo verificamos que esté registrada
        # No necesitamos insertar nada nuevo ya que las firmas están en usuarios_firma
        
        # Obtener la firma existente para la respuesta
        cur.execute("""
            SELECT uf.id FROM app.usuarios_firma uf
            JOIN app.beneficiarios b ON uf.rut = b.ben_run
            WHERE b.id = %s AND b.expediente_id = %s
        """, (beneficiario_id, expediente_id))
        
        firma_result = cur.fetchone()
        firma_id = firma_result[0] if firma_result else None
        
        # Obtener solicitud_id para verificar si puede cambiar a pendiente
        cur.execute("""
            SELECT id FROM app.solicitudes 
            WHERE expediente_id = %s 
            ORDER BY id DESC LIMIT 1
        """, (expediente_id,))
        
        solicitud_result = cur.fetchone()
        solicitud_id = solicitud_result[0] if solicitud_result else None
        
        # Verificar si la solicitud está lista para evaluación (todas las firmas + cálculo)
        if solicitud_id:
            verificar_y_actualizar_estado_pendiente(expediente_id, solicitud_id, cur, conn)
        
        conn.commit()
        cur.close()
        conn.close()
        
        print(f'✅ Firma de beneficiario registrada: {beneficiario[1]}')
        
        return jsonify({
            'success': True,
            'message': 'Firma de beneficiario verificada exitosamente',
            'data': {
                'firma_id': firma_id,
                'beneficiario_id': beneficiario_id,
                'expediente_id': expediente_id,
                'beneficiario': {
                    'nombre': beneficiario[1],
                    'rut': beneficiario[2]
                }
            }
        }), 200
        
    except Exception as e:
        print(f'❌ Error firmando beneficiario: {e}')
        if 'conn' in locals():
            conn.rollback()
            conn.close()
        return jsonify({'error': f'Error interno del servidor: {str(e)}'}), 500

@app.route('/api/expediente/<int:expediente_id>/firmas-beneficiarios', methods=['GET'])
@login_required
def obtener_firmas_beneficiarios(expediente_id):
    """Obtener todas las firmas de beneficiarios de un expediente"""
    print(f"🔔 Consultando firmas de beneficiarios para expediente: {expediente_id}")
    
    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Error de conexión a la base de datos'}), 500
    
    try:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        # Obtener firmas con datos de beneficiarios desde usuarios_firma
        cur.execute("""
            SELECT 
                uf.id as firma_id,
                uf.rut,
                b.id as beneficiario_id,
                b.ben_nombre,
                b.ben_run
            FROM app.usuarios_firma uf
            JOIN app.beneficiarios b ON uf.rut = b.ben_run
            WHERE b.expediente_id = %s
            ORDER BY uf.id DESC
        """, (expediente_id,))
        
        firmas = cur.fetchall()
        
        # Obtener total de beneficiarios del expediente
        cur.execute("""
            SELECT COUNT(*) as total_beneficiarios
            FROM app.beneficiarios 
            WHERE expediente_id = %s
        """, (expediente_id,))
        
        total_beneficiarios = cur.fetchone()['total_beneficiarios']
        
        cur.close()
        conn.close()
        
        return jsonify({
            'success': True,
            'data': {
                'expediente_id': expediente_id,
                'total_beneficiarios': total_beneficiarios,
                'beneficiarios_firmados': len(firmas),
                'beneficiarios_pendientes': total_beneficiarios - len(firmas),
                'firmas': [dict(firma) for firma in firmas]
            }
        }), 200
        
    except Exception as e:
        print(f'❌ Error consultando firmas de beneficiarios: {e}')
        if 'conn' in locals():
            conn.close()
        return jsonify({'error': f'Error interno del servidor: {str(e)}'}), 500

@app.route('/api/buscar-saldo-insoluto', methods=['POST'])
@login_required
def buscar_saldo_insoluto():
    """Buscar saldos insolutos por RUT del causante"""
    print("🔔 Petición de búsqueda de saldo insoluto")
    
    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Error de conexión a la base de datos'}), 500
    
    try:
        data = request.get_json()
        
        # Validar datos requeridos
        if not data.get('rut'):
            return jsonify({'error': 'RUT es requerido'}), 400
        
        rut = data['rut'].strip()
        
        # Validar formato básico de RUT (sin validación matemática estricta)
        rut_limpio = rut.replace('.', '').replace('-', '').upper()
        if len(rut_limpio) < 8 or len(rut_limpio) > 9:
            return jsonify({'error': 'Formato de RUT inválido'}), 400
        
        if not rut_limpio[:-1].isdigit() or rut_limpio[-1] not in '0123456789K':
            return jsonify({'error': 'Formato de RUT inválido'}), 400
        
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        # Buscar expedientes por RUT del causante
        cur.execute("""
            SELECT DISTINCT
                e.id as expediente_id,
                e.expediente_numero,
                e.estado as estado_expediente,
                e.observaciones,
                c.fal_nombre,
                c.fal_apellido_p,
                c.fal_apellido_m,
                c.fal_run,
                c.fal_fecha_defuncion,
                c.fal_comuna_defuncion,
                s.folio,
                s.estado as estado_solicitud,
                s.sucursal,
                e.fecha_creacion,
                COUNT(b.id) as total_beneficiarios,
                COUNT(uf.id) as beneficiarios_firmados
            FROM app.expediente e
            JOIN app.causante c ON e.id = c.expediente_id
            JOIN app.solicitudes s ON e.id = s.expediente_id
            LEFT JOIN app.beneficiarios b ON e.id = b.expediente_id
            LEFT JOIN app.usuarios_firma uf ON b.ben_run = uf.rut
            WHERE c.fal_run = %s
            GROUP BY e.id, e.expediente_numero, e.estado, e.observaciones, e.fecha_creacion,
                     c.fal_nombre, c.fal_apellido_p, c.fal_apellido_m, c.fal_run,
                     c.fal_fecha_defuncion, c.fal_comuna_defuncion,
                     s.folio, s.estado, s.sucursal
            ORDER BY e.fecha_creacion DESC
        """, (rut,))
        
        expedientes = cur.fetchall()
        
        if not expedientes:
            cur.close()
            conn.close()
            return jsonify({
                'success': True,
                'message': 'No se encontraron saldos insolutos para el RUT proporcionado',
                'data': {
                    'rut': rut,
                    'expedientes': [],
                    'total': 0
                }
            }), 200
        
        # Procesar resultados
        resultados = []
        for exp in expedientes:
            # Calcular estado de firmas
            pendientes_firmas = exp['total_beneficiarios'] - exp['beneficiarios_firmados']
            
            # Determinar estado general
            if exp['estado_solicitud'] == 'completado':
                estado_general = 'Completado'
                color_estado = '#28a745'
            elif pendientes_firmas == 0 and exp['total_beneficiarios'] > 0:
                estado_general = 'Firmas Completas'
                color_estado = '#17a2b8'
            elif pendientes_firmas > 0:
                estado_general = f'Pendiente ({pendientes_firmas} firmas)'
                color_estado = '#ffc107'
            else:
                estado_general = 'En Proceso'
                color_estado = '#6c757d'
            
            resultado = {
                'expediente_id': exp['expediente_id'],
                'expediente_numero': exp['expediente_numero'],
                'folio': exp['folio'],
                'causante': {
                    'nombre_completo': f"{exp['fal_nombre']} {exp['fal_apellido_p']} {exp['fal_apellido_m'] or ''}".strip(),
                    'rut': exp['fal_run'],
                    'fecha_defuncion': exp['fal_fecha_defuncion'].strftime('%d/%m/%Y') if exp['fal_fecha_defuncion'] else 'No especificada',
                    'sucursal': exp['sucursal'] or 'No especificada'
                },
                'solicitud': {
                    'fecha_creacion': exp['fecha_creacion'].strftime('%d/%m/%Y %H:%M') if exp['fecha_creacion'] else 'No especificada',
                    'estado': exp['estado_solicitud']
                },
                'firmas': {
                    'total_beneficiarios': exp['total_beneficiarios'],
                    'beneficiarios_firmados': exp['beneficiarios_firmados'],
                    'pendientes': pendientes_firmas
                },
                'estado_general': estado_general,
                'color_estado': color_estado
            }
            resultados.append(resultado)
        
        cur.close()
        conn.close()
        
        print(f'✅ Búsqueda exitosa para RUT {rut}: {len(resultados)} expedientes encontrados')
        
        return jsonify({
            'success': True,
            'message': f'Se encontraron {len(resultados)} saldo(s) insoluto(s)',
            'data': {
                'rut': rut,
                'expedientes': resultados,
                'total': len(resultados)
            }
        }), 200
        
    except Exception as e:
        print(f'❌ Error en búsqueda de saldo insoluto: {e}')
        if 'conn' in locals():
            conn.close()
        return jsonify({'error': f'Error interno del servidor: {str(e)}'}), 500

@app.route('/api/expediente/<int:expediente_id>/actualizar', methods=['PUT'])
@login_required
def actualizar_expediente(expediente_id):
    """Actualizar datos de un expediente rechazado (solo si está rechazado)"""
    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Error de conexión a la base de datos'}), 500
    
    try:
        data = request.get_json()
        funcionario_id = session.get('user_id')
        
        cur = conn.cursor()
        
        # Verificar que el expediente existe y está rechazado
        cur.execute("""
            SELECT e.id, e.funcionario_id, s.estado 
            FROM app.expediente e
            JOIN app.solicitudes s ON e.id = s.expediente_id
            WHERE e.id = %s
            ORDER BY s.id DESC LIMIT 1
        """, (expediente_id,))
        
        expediente_check = cur.fetchone()
        
        if not expediente_check:
            cur.close()
            conn.close()
            return jsonify({'error': 'Expediente no encontrado'}), 404
        
        # Verificar que el expediente está rechazado/enRevision (no bloqueado)
        estado_actual = expediente_check[2]
        if estado_actual == 'pendiente':
            cur.close()
            conn.close()
            return jsonify({'error': 'No se puede editar un expediente que está en revisión de jefatura. Debe estar rechazado para poder editarlo.'}), 400
        
        if estado_actual != 'rechazado/enRevision':
            cur.close()
            conn.close()
            return jsonify({'error': 'Solo se pueden editar expedientes rechazados que están en revisión'}), 400
        
        # Actualizar causante si se proporciona
        if data.get('causante'):
            causante_data = data['causante']
            nombre_completo = causante_data.get('nombre_completo') or ''
            nombre_parts = nombre_completo.split(' ', 2)
            
            cur.execute("""
                UPDATE app.causante 
                SET fal_nombre = %s,
                    fal_apellido_p = %s,
                    fal_apellido_m = %s,
                    fal_fecha_defuncion = %s,
                    fal_comuna_defuncion = %s,
                    fal_nacionalidad = %s
                WHERE expediente_id = %s
            """, (
                nombre_parts[0] if len(nombre_parts) > 0 else None,
                nombre_parts[1] if len(nombre_parts) > 1 else None,
                nombre_parts[2] if len(nombre_parts) > 2 else None,
                causante_data.get('fecha_defuncion') or None,
                causante_data.get('comuna_defuncion') or None,
                causante_data.get('nacionalidad') or None,
                expediente_id
            ))
        
        # Actualizar representante si se proporciona
        if data.get('representante'):
            rep_data = data['representante']
            nombre_completo = rep_data.get('nombre_completo') or ''
            nombre_parts = nombre_completo.split(' ', 2)
            
            cur.execute("""
                UPDATE app.representante 
                SET rep_nombre = %s,
                    rep_apellido_p = %s,
                    rep_apellido_m = %s,
                    rep_rut = %s,
                    rep_calidad = %s,
                    rep_telefono = %s,
                    rep_email = %s
                WHERE expediente_id = %s
            """, (
                nombre_parts[0] if len(nombre_parts) > 0 else None,
                nombre_parts[1] if len(nombre_parts) > 1 else None,
                nombre_parts[2] if len(nombre_parts) > 2 else None,
                rep_data.get('rut') or None,
                rep_data.get('calidad') or None,
                rep_data.get('telefono') or None,
                rep_data.get('email') or None,
                expediente_id
            ))
        
        # Actualizar beneficiarios si se proporciona
        if data.get('beneficiarios'):
            beneficiarios_data = data['beneficiarios']
            for ben in beneficiarios_data:
                ben_id = ben.get('id')
                # Si tiene ID y no empieza con 'nuevo-', es un beneficiario existente
                if ben_id and not str(ben_id).startswith('nuevo-'):
                    # Actualizar beneficiario existente
                    cur.execute("""
                        UPDATE app.beneficiarios 
                        SET ben_nombre = %s,
                            ben_run = %s,
                            ben_parentesco = %s
                        WHERE id = %s AND expediente_id = %s
                    """, (
                        ben.get('nombre'),
                        ben.get('rut'),
                        ben.get('parentesco'),
                        ben_id,
                        expediente_id
                    ))
                else:
                    # Crear nuevo beneficiario
                    cur.execute("""
                        INSERT INTO app.beneficiarios (expediente_id, solicitud_id, ben_nombre, ben_run, ben_parentesco)
                        SELECT %s, s.id, %s, %s, %s
                        FROM app.solicitudes s
                        WHERE s.expediente_id = %s
                        ORDER BY s.id DESC LIMIT 1
                    """, (
                        expediente_id,
                        ben.get('nombre'),
                        ben.get('rut'),
                        ben.get('parentesco'),
                        expediente_id
                    ))
        
        # Actualizar sucursal en solicitud si se proporciona
        if data.get('sucursal'):
            cur.execute("""
                UPDATE app.solicitudes 
                SET sucursal = %s
                WHERE expediente_id = %s AND estado = 'rechazado/enRevision'
            """, (data['sucursal'], expediente_id))
        
        conn.commit()
        cur.close()
        conn.close()
        
        return jsonify({
            'success': True,
            'message': 'Expediente actualizado exitosamente'
        }), 200
        
    except Exception as e:
        print(f'❌ Error actualizando expediente: {e}')
        if 'conn' in locals():
            conn.rollback()
            conn.close()
        return jsonify({'error': f'Error interno del servidor: {str(e)}'}), 500

@app.route('/api/beneficiarios/<int:beneficiario_id>', methods=['DELETE'])
@login_required
def eliminar_beneficiario(beneficiario_id):
    """Eliminar un beneficiario"""
    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Error de conexión a la base de datos'}), 500
    
    try:
        cur = conn.cursor()
        
        # Verificar que el beneficiario existe y pertenece a un expediente rechazado/enRevision
        cur.execute("""
            SELECT b.id, b.expediente_id, s.estado
            FROM app.beneficiarios b
            JOIN app.solicitudes s ON b.expediente_id = s.expediente_id
            WHERE b.id = %s
            ORDER BY s.id DESC LIMIT 1
        """, (beneficiario_id,))
        
        beneficiario = cur.fetchone()
        if not beneficiario:
            cur.close()
            conn.close()
            return jsonify({'error': 'Beneficiario no encontrado'}), 404
        
        estado = beneficiario[2]
        if estado != 'rechazado/enRevision':
            cur.close()
            conn.close()
            return jsonify({'error': 'Solo se pueden eliminar beneficiarios de expedientes rechazados en revisión'}), 400
        
        # Eliminar beneficiario
        cur.execute("DELETE FROM app.beneficiarios WHERE id = %s", (beneficiario_id,))
        
        conn.commit()
        cur.close()
        conn.close()
        
        return jsonify({
            'success': True,
            'message': 'Beneficiario eliminado exitosamente'
        }), 200
        
    except Exception as e:
        print(f'❌ Error eliminando beneficiario: {e}')
        if 'conn' in locals():
            conn.rollback()
            conn.close()
        return jsonify({'error': f'Error interno del servidor: {str(e)}'}), 500

@app.route('/api/documentos/<int:documento_id>', methods=['DELETE'])
@login_required
def eliminar_documento(documento_id):
    """Eliminar un documento"""
    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Error de conexión a la base de datos'}), 500
    
    try:
        cur = conn.cursor()
        
        # Verificar que el documento existe y pertenece a un expediente rechazado/enRevision
        cur.execute("""
            SELECT d.id, d.expediente_id, s.estado
            FROM app.documentos_saldo_insoluto d
            JOIN app.solicitudes s ON d.expediente_id = s.expediente_id
            WHERE d.id = %s
            ORDER BY s.id DESC LIMIT 1
        """, (documento_id,))
        
        documento = cur.fetchone()
        if not documento:
            cur.close()
            conn.close()
            return jsonify({'error': 'Documento no encontrado'}), 404
        
        estado = documento[2]
        if estado != 'rechazado/enRevision':
            cur.close()
            conn.close()
            return jsonify({'error': 'Solo se pueden eliminar documentos de expedientes rechazados en revisión'}), 400
        
        # Eliminar documento
        cur.execute("DELETE FROM app.documentos_saldo_insoluto WHERE id = %s", (documento_id,))
        
        conn.commit()
        cur.close()
        conn.close()
        
        return jsonify({
            'success': True,
            'message': 'Documento eliminado exitosamente'
        }), 200
        
    except Exception as e:
        print(f'❌ Error eliminando documento: {e}')
        if 'conn' in locals():
            conn.rollback()
            conn.close()
        return jsonify({'error': f'Error interno del servidor: {str(e)}'}), 500

@app.route('/api/revision-expediente', methods=['POST'])
def revision_expediente():
    """Obtener expediente completo por RUT del causante para revisión"""
    print("🔔 Petición de revisión de expediente")
    
    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Error de conexión a la base de datos'}), 500
    
    try:
        data = request.get_json()
        
        # Validar datos requeridos
        if not data.get('rut'):
            return jsonify({'error': 'RUT es requerido'}), 400
        
        rut = data['rut'].strip()
        
        # Validar formato básico de RUT
        rut_limpio = rut.replace('.', '').replace('-', '').upper()
        if len(rut_limpio) < 8 or len(rut_limpio) > 9:
            return jsonify({'error': 'Formato de RUT inválido'}), 400
        
        if not rut_limpio[:-1].isdigit() or rut_limpio[-1] not in '0123456789K':
            return jsonify({'error': 'Formato de RUT inválido'}), 400
        
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        # Obtener expediente completo por RUT del causante
        cur.execute("""
            SELECT DISTINCT
                e.id as expediente_id,
                e.expediente_numero,
                e.estado as estado_expediente,
                e.observaciones,
                e.fecha_creacion,
                e.funcionario_id,
                f.iniciales as funcionario_iniciales,
                f.nombres as funcionario_nombres,
                f.apellido_p as funcionario_apellido_p,
                f.apellido_m as funcionario_apellido_m,
                c.fal_nombre,
                c.fal_apellido_p,
                c.fal_apellido_m,
                c.fal_run,
                c.fal_fecha_defuncion,
                c.fal_comuna_defuncion,
                c.fal_nacionalidad,
                s.id as solicitud_id,
                s.folio,
                s.estado as estado_solicitud,
                s.firmado_funcionario,
                s.sucursal,
                s.observacion as motivo_solicitud,
                r.rep_nombre,
                r.rep_apellido_p,
                r.rep_apellido_m,
                r.rep_rut,
                r.rep_calidad,
                r.rep_telefono,
                r.rep_email,
                COUNT(DISTINCT b.id) as total_beneficiarios,
                COUNT(DISTINCT uf.id) as beneficiarios_firmados,
                COUNT(DISTINCT d.id) as total_documentos
            FROM app.expediente e
            JOIN app.causante c ON e.id = c.expediente_id
            JOIN app.solicitudes s ON e.id = s.expediente_id
            LEFT JOIN app.funcionarios f ON e.funcionario_id = f.id
            LEFT JOIN app.representante r ON e.id = r.expediente_id
            LEFT JOIN app.beneficiarios b ON e.id = b.expediente_id
            LEFT JOIN app.usuarios_firma uf ON b.ben_run = uf.rut
            LEFT JOIN app.documentos_saldo_insoluto d ON e.id = d.expediente_id
            WHERE c.fal_run = %s
            GROUP BY e.id, e.expediente_numero, e.estado, e.observaciones, e.fecha_creacion, e.funcionario_id,
                     f.iniciales, f.nombres, f.apellido_p, f.apellido_m,
                     c.fal_nombre, c.fal_apellido_p, c.fal_apellido_m, c.fal_run,
                     c.fal_fecha_defuncion, c.fal_comuna_defuncion, c.fal_nacionalidad,
                     s.id, s.folio, s.estado, s.firmado_funcionario, s.sucursal, s.observacion,
                     r.rep_nombre, r.rep_apellido_p, r.rep_apellido_m, r.rep_rut,
                     r.rep_calidad, r.rep_telefono, r.rep_email
            ORDER BY e.fecha_creacion DESC
        """, (rut,))
        
        expediente = cur.fetchone()
        
        if not expediente:
            cur.close()
            conn.close()
            return jsonify({
                'success': True,
                'message': 'No se encontró expediente para el RUT proporcionado',
                'data': {
                    'rut': rut,
                    'expediente': None,
                    'documentos': [],
                    'beneficiarios': []
                }
            }), 200
        
        # Obtener beneficiarios del expediente
        cur.execute("""
            SELECT 
                b.id,
                b.expediente_id,
                b.ben_nombre,
                b.ben_run,
                b.ben_parentesco,
                uf.id as firma_id,
                uf.rut as firma_rut
            FROM app.beneficiarios b
            LEFT JOIN app.usuarios_firma uf ON b.ben_run = uf.rut
            WHERE b.expediente_id = %s
            ORDER BY b.id
        """, (expediente['expediente_id'],))
        
        beneficiarios = cur.fetchall()
        
        # Obtener documentos del expediente
        cur.execute("""
            SELECT 
                d.id,
                d.doc_nombre_archivo,
                d.doc_tipo_id,
                d.doc_tamano_bytes,
                d.doc_mime_type,
                d.doc_fecha_subida,
                d.doc_estado,
                d.doc_ruta_storage
            FROM app.documentos_saldo_insoluto d
            WHERE d.expediente_id = %s
            ORDER BY d.doc_fecha_subida DESC
        """, (expediente['expediente_id'],))
        
        documentos = cur.fetchall()
        
        # Determinar estado de firma del representante ANTES de cerrar el cursor
        representante_firmado = False
        
        if expediente['rep_rut']:
            # Verificar si el RUT del representante está en usuarios_firma (ignorando mayúsculas/minúsculas)
            cur.execute("""
                SELECT id FROM app.usuarios_firma 
                WHERE UPPER(rut) = UPPER(%s)
            """, (expediente['rep_rut'],))
            
            if cur.fetchone():
                representante_firmado = True
            else:
                representante_firmado = False
        
        cur.close()
        conn.close()
        
        # Procesar datos del expediente
        pendientes_firmas_beneficiarios = expediente['total_beneficiarios'] - expediente['beneficiarios_firmados']
        
        # Calcular total de firmas (beneficiarios + representante)
        total_firmas = expediente['total_beneficiarios'] + 1  # +1 por el representante
        firmas_completadas = expediente['beneficiarios_firmados'] + (1 if representante_firmado else 0)
        pendientes_firmas = total_firmas - firmas_completadas
        
        # Determinar estado de firmas
        if total_firmas == 1:  # Solo representante, sin beneficiarios
            estado_firmas = 'Solo representante'
            color_firmas = '#6c757d'
            icono_firmas = '👨‍💼'
        elif pendientes_firmas == 0:
            estado_firmas = 'Firmas completas'
            color_firmas = '#28a745'
            icono_firmas = '✅'
        else:
            estado_firmas = f'Pendientes: {pendientes_firmas}'
            color_firmas = '#ffc107'
            icono_firmas = '⚠️'
        
        # Procesar beneficiarios
        beneficiarios_procesados = []
        for ben in beneficiarios:
            beneficiario = {
                'id': ben['id'],
                'expediente_id': ben['expediente_id'],
                'nombre_completo': ben['ben_nombre'] or 'Sin nombre',
                'rut': ben['ben_run'],
                'parentesco': ben['ben_parentesco'],
                'firma': {
                    'firmado': ben['firma_id'] is not None,
                    'rut_firma': ben['firma_rut'] if ben['firma_rut'] else None
                }
            }
            beneficiarios_procesados.append(beneficiario)
        
        # Procesar documentos
        documentos_procesados = []
        for doc in documentos:
            tamano_mb = (doc['doc_tamano_bytes'] / (1024 * 1024)) if doc['doc_tamano_bytes'] else 0
            
            documento = {
                'id': doc['id'],
                'nombre': doc['doc_nombre_archivo'],
                'tipo_id': doc['doc_tipo_id'],
                'tamano_mb': round(tamano_mb, 2),
                'mime_type': doc['doc_mime_type'],
                'fecha_subida': doc['doc_fecha_subida'].strftime('%d/%m/%Y %H:%M') if doc['doc_fecha_subida'] else 'No especificada',
                'estado': doc['doc_estado'],
                'ruta_descarga': doc['doc_ruta_storage']
            }
            documentos_procesados.append(documento)
        
        resultado = {
            'expediente_id': expediente['expediente_id'],
            'expediente_numero': expediente['expediente_numero'],
            'folio': expediente['folio'],
            'estado_expediente': expediente['estado_expediente'],
            'fecha_creacion': expediente['fecha_creacion'].strftime('%d/%m/%Y %H:%M') if expediente['fecha_creacion'] else 'No especificada',
            'causante': {
                'nombre_completo': f"{expediente['fal_nombre']} {expediente['fal_apellido_p']} {expediente['fal_apellido_m'] or ''}".strip(),
                'rut': expediente['fal_run'],
                'fecha_defuncion': expediente['fal_fecha_defuncion'].strftime('%Y-%m-%d') if expediente['fal_fecha_defuncion'] else None,
                'comuna_defuncion': expediente['fal_comuna_defuncion'] or 'No especificada',
                'nacionalidad': expediente['fal_nacionalidad'] or 'No especificada'
            },
            'representante': {
                'nombre_completo': f"{expediente['rep_nombre'] or ''} {expediente['rep_apellido_p'] or ''} {expediente['rep_apellido_m'] or ''}".strip() if expediente['rep_nombre'] else 'No especificado',
                'rut': expediente['rep_rut'] or 'No especificado',
                'calidad': expediente['rep_calidad'] or 'No especificada',
                'telefono': expediente['rep_telefono'] or 'No especificado',
                'email': expediente['rep_email'] or 'No especificado',
                'firmado': representante_firmado
            },
            'solicitud': {
                'id': expediente['solicitud_id'],
                'sucursal': expediente['sucursal'] or 'No especificada',
                'motivo': expediente['motivo_solicitud'] or 'No especificado',
                'estado': expediente['estado_solicitud'],
                'firmado_funcionario': expediente.get('firmado_funcionario', False)
            },
            'funcionario': {
                'id': expediente['funcionario_id'] or 'No especificado',
                'iniciales': expediente['funcionario_iniciales'] or 'No especificado',
                'nombre_completo': f"{expediente['funcionario_nombres'] or ''} {expediente['funcionario_apellido_p'] or ''} {expediente['funcionario_apellido_m'] or ''}".strip() if expediente['funcionario_nombres'] else 'No especificado'
            },
            'firmas': {
                'total_firmas': total_firmas,
                'firmas_completadas': firmas_completadas,
                'pendientes': pendientes_firmas,
                'estado': estado_firmas,
                'color': color_firmas,
                'icono': icono_firmas,
                'detalle': {
                    'beneficiarios': {
                        'total': expediente['total_beneficiarios'],
                        'firmados': expediente['beneficiarios_firmados'],
                        'pendientes': pendientes_firmas_beneficiarios
                    },
                    'representante': {
                        'firmado': representante_firmado
                    }
                }
            },
            'documentos': {
                'total': expediente['total_documentos'],
                'lista': documentos_procesados
            },
            'beneficiarios': beneficiarios_procesados
        }
        
        print(f'✅ Revisión exitosa para RUT {rut}: Expediente {expediente["expediente_numero"]}')
        
        return jsonify({
            'success': True,
            'message': f'Expediente encontrado: {expediente["expediente_numero"]}',
            'data': resultado
        }), 200
        
    except Exception as e:
        print(f'❌ Error en revisión de expediente: {e}')
        if 'conn' in locals():
            conn.close()
        return jsonify({'error': f'Error interno del servidor: {str(e)}'}), 500

@app.route('/api/solicitudes-pendientes', methods=['GET'])
@login_required
def solicitudes_pendientes():
    """Obtener solicitudes pendientes de aprobación por jefatura"""
    print("🔔 Petición de solicitudes pendientes")
    
    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Error de conexión a la base de datos'}), 500
    
    try:
        estado_filtro = request.args.get('estado', '')
        sucursal_filtro = request.args.get('sucursal', '')
        
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        # Construir consulta base
        query = """
            SELECT DISTINCT
                e.id as expediente_id,
                e.expediente_numero,
                e.fecha_creacion,
                s.id as solicitud_id,
                s.folio,
                s.estado as estado_solicitud,
                s.firmado_funcionario,
                s.sucursal,
                c.fal_nombre || ' ' || c.fal_apellido_p || ' ' || COALESCE(c.fal_apellido_m, '') as causante_nombre_completo,
                c.fal_run as causante_rut,
                c.fal_fecha_defuncion as causante_fecha_defuncion,
                r.rep_nombre || ' ' || COALESCE(r.rep_apellido_p, '') || ' ' || COALESCE(r.rep_apellido_m, '') as representante_nombre_completo,
                r.rep_rut as representante_rut,
                r.rep_calidad as representante_calidad,
                COUNT(DISTINCT b.id) as total_beneficiarios,
                COUNT(DISTINCT uf.id) as beneficiarios_firmados,
                COUNT(DISTINCT d.id) as total_documentos
            FROM app.expediente e
            JOIN app.solicitudes s ON e.id = s.expediente_id
            JOIN app.causante c ON e.id = c.expediente_id
            LEFT JOIN app.representante r ON e.id = r.expediente_id
            LEFT JOIN app.beneficiarios b ON e.id = b.expediente_id
            LEFT JOIN app.usuarios_firma uf ON b.ben_run = uf.rut
            LEFT JOIN app.documentos_saldo_insoluto d ON e.id = d.expediente_id
            WHERE 1=1
        """
        
        params = []
        
        # Filtro por estado
        if estado_filtro:
            # Filtrar por estado exacto (pendiente o completado)
            query += " AND s.estado = %s"
            params.append(estado_filtro)
        else:
            # Por defecto, mostrar solo pendientes (en revisión)
            query += " AND s.estado = 'pendiente'"
        
        # Filtro por sucursal
        if sucursal_filtro:
            query += " AND s.sucursal = %s"
            params.append(sucursal_filtro)
        
        query += """
            GROUP BY e.id, e.expediente_numero, e.fecha_creacion,
                     s.id, s.folio, s.estado, s.firmado_funcionario, s.sucursal,
                     c.fal_nombre, c.fal_apellido_p, c.fal_apellido_m, c.fal_run, c.fal_fecha_defuncion,
                     r.rep_nombre, r.rep_apellido_p, r.rep_apellido_m, r.rep_rut, r.rep_calidad
            ORDER BY e.fecha_creacion DESC
        """
        
        cur.execute(query, tuple(params))
        solicitudes = cur.fetchall()
        
        # Procesar resultado
        resultados = []
        for s in solicitudes:
            pendientes_firmas = (s['total_beneficiarios'] or 0) - (s['beneficiarios_firmados'] or 0)
            
            # Obtener documentos del expediente
            cur.execute("""
                SELECT 
                    d.id,
                    d.doc_nombre_archivo,
                    d.doc_tipo_id,
                    d.doc_tamano_bytes,
                    d.doc_mime_type,
                    d.doc_fecha_subida,
                    d.doc_estado,
                    d.doc_ruta_storage
                FROM app.documentos_saldo_insoluto d
                WHERE d.expediente_id = %s
                ORDER BY d.doc_fecha_subida DESC
            """, (s['expediente_id'],))
            
            documentos_db = cur.fetchall()
            documentos_lista = []
            for doc in documentos_db:
                tamano_mb = (doc['doc_tamano_bytes'] / (1024 * 1024)) if doc['doc_tamano_bytes'] else 0
                documentos_lista.append({
                    'id': doc['id'],
                    'nombre': doc['doc_nombre_archivo'],
                    'tipo_id': doc['doc_tipo_id'],
                    'tamano_mb': round(tamano_mb, 2),
                    'mime_type': doc['doc_mime_type'],
                    'fecha_subida': doc['doc_fecha_subida'].strftime('%d/%m/%Y %H:%M') if doc['doc_fecha_subida'] else 'No especificada',
                    'estado': doc['doc_estado'],
                    'ruta_descarga': doc['doc_ruta_storage']
                })
            
            # Verificar si representante tiene firma
            representante_firmado = False
            if s['representante_rut']:
                cur.execute("""
                    SELECT id FROM app.usuarios_firma 
                    WHERE UPPER(rut) = UPPER(%s)
                """, (s['representante_rut'],))
                if cur.fetchone():
                    representante_firmado = True
            
            # Obtener beneficiarios del expediente
            cur.execute("""
                SELECT 
                    b.id,
                    b.expediente_id,
                    b.ben_nombre,
                    b.ben_run,
                    b.ben_parentesco,
                    uf.id as firma_id,
                    uf.rut as firma_rut
                FROM app.beneficiarios b
                LEFT JOIN app.usuarios_firma uf ON b.ben_run = uf.rut
                WHERE b.expediente_id = %s
                ORDER BY b.id
            """, (s['expediente_id'],))
            
            beneficiarios_db = cur.fetchall()
            beneficiarios_lista = []
            for ben in beneficiarios_db:
                beneficiarios_lista.append({
                    'id': ben['id'],
                    'expediente_id': ben['expediente_id'],
                    'nombre_completo': ben['ben_nombre'] or 'Sin nombre',
                    'rut': ben['ben_run'],
                    'parentesco': ben['ben_parentesco'],
                    'firma': {
                        'firmado': ben['firma_id'] is not None,
                        'rut_firma': ben['firma_rut'] if ben['firma_rut'] else None
                    }
                })
            
            resultados.append({
                'expediente_id': s['expediente_id'],
                'solicitud_id': s['solicitud_id'],
                'folio': s['folio'],
                'estado_solicitud': s['estado_solicitud'],
                'firmado_funcionario': s.get('firmado_funcionario', False),
                'fecha_creacion': s['fecha_creacion'].isoformat() if s['fecha_creacion'] else None,
                'sucursal': s['sucursal'],
                'causante': {
                    'nombre_completo': s['causante_nombre_completo'],
                    'rut': s['causante_rut'],
                    'fecha_defuncion': s['causante_fecha_defuncion'].isoformat() if s['causante_fecha_defuncion'] else None
                },
                'representante': {
                    'nombre_completo': s['representante_nombre_completo'] or 'No especificado',
                    'rut': s['representante_rut'] or 'No especificado',
                    'calidad': s['representante_calidad'] or 'No especificada',
                    'firmado': representante_firmado
                },
                'firmas': {
                    'total_beneficiarios': s['total_beneficiarios'] or 0,
                    'beneficiarios_firmados': s['beneficiarios_firmados'] or 0,
                    'pendientes': max(0, pendientes_firmas)
                },
                'documentos': {
                    'total': s['total_documentos'] or 0,
                    'lista': documentos_lista
                },
                'beneficiarios': beneficiarios_lista
            })
        
        cur.close()
        conn.close()
        
        return jsonify({
            'success': True,
            'data': resultados
        }), 200
        
    except Exception as e:
        print(f'❌ Error obteniendo solicitudes pendientes: {e}')
        if 'conn' in locals():
            conn.close()
        return jsonify({'error': f'Error interno del servidor: {str(e)}'}), 500

@app.route('/api/login', methods=['POST'])
def login():
    """Autenticar funcionario y crear sesión"""
    data = request.get_json()
    username = data.get('username')  # En este caso será el RUT
    password = data.get('password')
    
    if not username or not password:
        return jsonify({'error': 'RUT y contraseña requeridos'}), 400
    
    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Error de conexión a la base de datos'}), 500
    
    try:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("""
            SELECT id, rut, nombres, apellido_p, apellido_m, password_hash, rol, sucursal, iniciales
            FROM app.funcionarios 
            WHERE rut = %s AND activo = true
        """, (username,))
        
        funcionario = cur.fetchone()
        cur.close()
        conn.close()
        
        if funcionario and bcrypt.checkpw(password.encode('utf-8'), funcionario['password_hash'].encode('utf-8')):
            # Crear sesión
            session['user_id'] = funcionario['id']
            session['username'] = funcionario['rut']
            session['nombres'] = funcionario['nombres']
            session['apellido_p'] = funcionario['apellido_p']
            session['rol'] = funcionario['rol']
            session.permanent = True
            
            return jsonify({
                'success': True,
                'message': 'Login exitoso',
                'user': {
                    'id': funcionario['id'],
                    'rut': funcionario['rut'],
                    'nombres': funcionario['nombres'],
                    'apellido_p': funcionario['apellido_p'],
                    'rol': funcionario['rol']
                }
            }), 200
        else:
            return jsonify({'error': 'RUT o contraseña incorrectos'}), 401
            
    except Exception as e:
        print(f'❌ Error en login: {e}')
        if 'conn' in locals():
            conn.close()
        return jsonify({'error': f'Error interno del servidor: {str(e)}'}), 500

@app.route('/api/logout', methods=['POST'])
def logout():
    """Cerrar sesión"""
    session.clear()
    return jsonify({'success': True, 'message': 'Sesión cerrada exitosamente'}), 200

@app.route('/api/check-session', methods=['GET'])
def check_session():
    """Verificar si hay sesión activa"""
    if 'user_id' in session:
        return jsonify({
            'authenticated': True,
            'user': {
                'id': session['user_id'],
                'rut': session['username'],
                'nombres': session.get('nombres', ''),
                'apellido_p': session.get('apellido_p', ''),
                'rol': session.get('rol', '')
            }
        }), 200
    else:
        return jsonify({'authenticated': False}), 401

@app.route('/api/validar-clave-funcionario', methods=['POST'])
@login_required
def validar_clave_funcionario():
    """Validar la clave del funcionario logueado"""
    print("🔔 Petición de validación de clave de funcionario")
    
    data = request.get_json()
    password = data.get('password')
    
    if not password:
        return jsonify({'error': 'Contraseña requerida'}), 400
    
    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Error de conexión a la base de datos'}), 500
    
    try:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        # Obtener datos del funcionario logueado
        funcionario_id = session.get('user_id')
        cur.execute("""
            SELECT id, rut, nombres, apellido_p, apellido_m, password_hash, iniciales
            FROM app.funcionarios 
            WHERE id = %s AND activo = true
        """, (funcionario_id,))
        
        funcionario = cur.fetchone()
        cur.close()
        conn.close()
        
        if not funcionario:
            return jsonify({'error': 'Funcionario no encontrado'}), 404
        
        # Verificar la contraseña
        if bcrypt.checkpw(password.encode('utf-8'), funcionario['password_hash'].encode('utf-8')):
            nombre_completo = f"{funcionario['nombres']} {funcionario['apellido_p']} {funcionario['apellido_m'] or ''}".strip()
            
            return jsonify({
                'valid': True,
                'funcionario_id': funcionario['id'],
                'funcionario_nombre': nombre_completo,
                'funcionario_rut': funcionario['rut'],
                'funcionario_iniciales': funcionario['iniciales']
            }), 200
        else:
            return jsonify({
                'valid': False,
                'error': 'Contraseña incorrecta'
            }), 200
            
    except Exception as e:
        print(f'❌ Error validando clave de funcionario: {e}')
        if 'conn' in locals():
            conn.close()
        return jsonify({'error': f'Error interno del servidor: {str(e)}'}), 500

@app.route('/api/solicitudes/<int:solicitud_id>/firmar-funcionario', methods=['POST'])
@login_required
def firmar_solicitud_funcionario(solicitud_id):
    """Firmar solicitud como funcionario"""
    print(f"🔔 Petición de firma de funcionario para solicitud: {solicitud_id}")
    
    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Error de conexión a la base de datos'}), 500
    
    try:
        data = request.get_json()
        
        # Validar datos requeridos
        if not data.get('firma_data'):
            return jsonify({'error': 'Datos de firma requeridos'}), 400
        
        firma_data = data['firma_data']
        
        cur = conn.cursor()
        
        # Verificar que la solicitud existe
        cur.execute("SELECT id, expediente_id FROM app.solicitudes WHERE id = %s", (solicitud_id,))
        solicitud = cur.fetchone()
        
        if not solicitud:
            return jsonify({'error': 'Solicitud no encontrada'}), 404
        
        expediente_id = solicitud[1]
        
        # Obtener funcionario_id de la firma_data o de la sesión
        funcionario_id_firma = firma_data.get('funcionario_id') or session.get('user_id')
        
        print(f'🔍 funcionario_id_firma obtenido: {funcionario_id_firma}')
        print(f'🔍 firma_data contiene: {list(firma_data.keys())}')
        
        if not funcionario_id_firma:
            return jsonify({'error': 'No se pudo identificar al funcionario'}), 400
        
        # Verificar que el funcionario existe en la tabla funcionarios
        cur.execute("""
            SELECT id FROM app.funcionarios 
            WHERE id = %s AND activo = true
        """, (funcionario_id_firma,))
        
        funcionario = cur.fetchone()
        if not funcionario:
            return jsonify({'error': 'Funcionario no encontrado o inactivo'}), 404
        
        print(f'✅ Funcionario {funcionario_id_firma} verificado correctamente')
        
        # Verificar que las columnas existen, si no, intentar crearlas
        try:
            cur.execute("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_schema = 'app' 
                AND table_name = 'solicitudes' 
                AND column_name IN ('firmado_funcionario', 'fecha_firma_funcionario', 'funcionario_id_firma')
            """)
            columnas_existentes = [row[0] for row in cur.fetchall()]
            print(f'🔍 Columnas existentes: {columnas_existentes}')
            
            if 'firmado_funcionario' not in columnas_existentes:
                print('⚠️ Columnas no existen, intentando crearlas...')
                from utils.database import add_firma_funcionario_columns
                add_firma_funcionario_columns()
        except Exception as e:
            print(f'⚠️ Error verificando columnas: {e}')
        
        # Asegurar que las columnas existen antes de hacer UPDATE
        print('🔍 Verificando existencia de columnas...')
        cur.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_schema = 'app' 
            AND table_name = 'solicitudes' 
            AND column_name IN ('firmado_funcionario', 'fecha_firma_funcionario', 'funcionario_id_firma')
        """)
        columnas_existentes = [row[0] for row in cur.fetchall()]
        print(f'🔍 Columnas encontradas: {columnas_existentes}')
        
        if len(columnas_existentes) < 3:
            print('⚠️ Faltan columnas, creándolas ahora...')
            cur.close()
            conn.close()
            from utils.database import add_firma_funcionario_columns
            add_firma_funcionario_columns()
            conn = get_db_connection()
            cur = conn.cursor()
            print('✅ Columnas creadas, continuando con UPDATE...')
        
        # Actualizar solicitudes con la información de firma del funcionario
        print(f'📝 Ejecutando UPDATE en solicitud {solicitud_id} con funcionario_id={funcionario_id_firma}')
        cur.execute("""
            UPDATE app.solicitudes 
            SET firmado_funcionario = TRUE,
                fecha_firma_funcionario = NOW(),
                funcionario_id_firma = %s,
                estado = 'firmado_funcionario'
            WHERE id = %s
        """, (funcionario_id_firma, solicitud_id))
        
        print(f'📊 Rowcount después del UPDATE: {cur.rowcount}')
        
        # Verificar que el UPDATE de solicitud funcionó
        if cur.rowcount == 0:
            print(f'❌ ERROR: No se pudo actualizar solicitud {solicitud_id} - rowcount: {cur.rowcount}')
            print(f'🔍 Verificando si la solicitud existe...')
            cur.execute("SELECT id FROM app.solicitudes WHERE id = %s", (solicitud_id,))
            existe = cur.fetchone()
            if existe:
                print(f'⚠️ La solicitud existe pero el UPDATE no afectó filas. ¿Problema con las columnas?')
            else:
                print(f'⚠️ La solicitud {solicitud_id} NO existe')
            conn.rollback()
            cur.close()
            conn.close()
            return jsonify({'error': 'No se pudo actualizar el estado de la solicitud'}), 404
        
        print(f'✅ Solicitud {solicitud_id} actualizada EXITOSAMENTE - firmado_funcionario=TRUE, funcionario_id_firma={funcionario_id_firma}')
        
        # Actualizar validación con la firma del funcionario (mantener por compatibilidad)
        # Si falla, no hacer rollback porque ya actualizamos solicitudes
        try:
            cur.execute("""
                UPDATE app.validacion 
                SET val_firma_funcionario = %s,
                    val_estado = 'firmado_funcionario',
                    updated_at = NOW()
                WHERE solicitud_id = %s
            """, (json.dumps(firma_data), solicitud_id))
            
            if cur.rowcount == 0:
                print(f'⚠️ No se encontró registro de validación para solicitud {solicitud_id}, pero la solicitud ya fue actualizada')
            else:
                print(f'✅ Validación actualizada para solicitud {solicitud_id}')
        except Exception as e:
            print(f'⚠️ Error actualizando validación (no crítico): {e}')
        
        # Commit siempre para guardar los cambios de solicitudes
        print('💾 Ejecutando COMMIT...')
        conn.commit()
        print('✅ COMMIT ejecutado exitosamente')
        
        # Verificar que se guardó correctamente
        cur.execute("""
            SELECT firmado_funcionario, fecha_firma_funcionario, funcionario_id_firma 
            FROM app.solicitudes 
            WHERE id = %s
        """, (solicitud_id,))
        resultado = cur.fetchone()
        print(f'🔍 Verificación POST-COMMIT: firmado={resultado[0]}, fecha={resultado[1]}, funcionario_id={resultado[2]}')
        
        cur.close()
        conn.close()
        
        print(f'✅ Solicitud {solicitud_id} firmada por funcionario exitosamente')
        
        return jsonify({
            'success': True,
            'message': 'Solicitud firmada por funcionario exitosamente',
            'data': {
                'solicitud_id': solicitud_id,
                'expediente_id': expediente_id,
                'estado': 'firmado_funcionario',
                'nota': 'Representante firmará con aplicación externa'
            }
        }), 200
        
    except Exception as e:
        print(f'❌ Error firmando solicitud como funcionario: {e}')
        if 'conn' in locals():
            conn.rollback()
            conn.close()
        return jsonify({'error': f'Error interno del servidor: {str(e)}'}), 500

@app.route('/api/solicitudes/<int:solicitud_id>/firmar-funcionario-directo', methods=['POST'])
@login_required
def firmar_solicitud_funcionario_directo(solicitud_id):
    """Firmar solicitud como funcionario - Solo guarda en app.solicitudes"""
    print(f"🔔 Petición de firma DIRECTA de funcionario para solicitud: {solicitud_id}")
    
    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Error de conexión a la base de datos'}), 500
    
    try:
        data = request.get_json()
        firma_data = data.get('firma_data') if data else {}
        
        cur = conn.cursor()
        
        # Obtener funcionario_id de la firma_data o de la sesión
        funcionario_id_firma = firma_data.get('funcionario_id') if firma_data else None
        if not funcionario_id_firma:
            funcionario_id_firma = session.get('user_id')
        
        print(f'🔍 funcionario_id_firma: {funcionario_id_firma}')
        
        if not funcionario_id_firma:
            return jsonify({'error': 'No se pudo identificar al funcionario'}), 400
        
        # Verificar que el funcionario existe
        cur.execute("SELECT id FROM app.funcionarios WHERE id = %s AND activo = true", (funcionario_id_firma,))
        if not cur.fetchone():
            return jsonify({'error': 'Funcionario no encontrado o inactivo'}), 404
        
        # Crear columnas si no existen
        try:
            cur.execute("ALTER TABLE app.solicitudes ADD COLUMN IF NOT EXISTS firmado_funcionario BOOLEAN DEFAULT FALSE")
            conn.commit()
            print('✅ Columna firmado_funcionario verificada/creada')
        except Exception as e:
            print(f'⚠️ Error creando columna (puede que ya exista): {e}')
        
        # Obtener expediente_id antes de actualizar
        cur.execute("SELECT expediente_id FROM app.solicitudes WHERE id = %s", (solicitud_id,))
        expediente_result = cur.fetchone()
        if not expediente_result:
            conn.rollback()
            cur.close()
            conn.close()
            return jsonify({'error': f'Solicitud {solicitud_id} no encontrada'}), 404
        
        expediente_id = expediente_result[0]
        
        # UPDATE directo en solicitudes - SOLO firmado_funcionario
        cur.execute("""
            UPDATE app.solicitudes 
            SET firmado_funcionario = TRUE
            WHERE id = %s
        """, (solicitud_id,))
        
        print(f'📊 Rowcount: {cur.rowcount}')
        
        if cur.rowcount == 0:
            conn.rollback()
            cur.close()
            conn.close()
            return jsonify({'error': f'No se pudo actualizar solicitud {solicitud_id}'}), 404
        
        # Verificar si la solicitud está lista para evaluación (todas las firmas + cálculo)
        verificar_y_actualizar_estado_pendiente(expediente_id, solicitud_id, cur, conn)
        
        conn.commit()
        
        # Verificar que se guardó
        cur.execute("SELECT firmado_funcionario, estado FROM app.solicitudes WHERE id = %s", (solicitud_id,))
        resultado = cur.fetchone()
        print(f'✅ Guardado: firmado_funcionario={resultado[0]}, estado={resultado[1]}')
        
        cur.close()
        conn.close()
        
        return jsonify({
            'success': True,
            'message': 'Firma guardada en solicitudes exitosamente',
            'data': {
                'solicitud_id': solicitud_id,
                'firmado_funcionario': True
            }
        }), 200
        
    except Exception as e:
        print(f'❌ Error: {e}')
        if 'conn' in locals():
            conn.rollback()
            conn.close()
        return jsonify({'error': f'Error interno: {str(e)}'}), 500

@app.route('/api/download-expediente-completo/<int:expediente_id>', methods=['GET'])
@login_required
def download_expediente_completo(expediente_id):
    """Descargar todos los documentos del expediente como ZIP"""
    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Error de conexión a la base de datos'}), 500
    
    try:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        # Obtener todos los documentos del expediente
        cur.execute("""
            SELECT id, doc_nombre_archivo, doc_archivo_blob, doc_mime_type
            FROM app.documentos_saldo_insoluto 
            WHERE expediente_id = %s
            ORDER BY doc_fecha_subida ASC
        """, (expediente_id,))
        
        documentos = cur.fetchall()
        
        if not documentos:
            return jsonify({'error': 'No hay documentos en este expediente'}), 404
        
        # Crear ZIP en memoria
        zip_buffer = io.BytesIO()
        
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            for i, documento in enumerate(documentos):
                # Usar el nombre del archivo original
                zip_file.writestr(documento['doc_nombre_archivo'], documento['doc_archivo_blob'])
        
        zip_buffer.seek(0)
        
        cur.close()
        conn.close()
        
        print(f'📦 Generando ZIP con {len(documentos)} documentos para expediente {expediente_id}')
        
        return send_file(
            zip_buffer,
            mimetype='application/zip',
            as_attachment=True,
            download_name=f'expediente_{expediente_id}_completo.zip'
        )
        
    except Exception as e:
        print(f'❌ Error generando ZIP: {e}')
        if 'conn' in locals():
            conn.close()
        return jsonify({'error': f'Error interno del servidor: {str(e)}'}), 500

@app.route('/api/calcular-saldo-insoluto', methods=['POST'])
@login_required
def guardar_calculo_saldo():
    """Guardar cálculo de saldo insoluto"""
    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Error de conexión a la base de datos'}), 500
    
    try:
        data = request.get_json()
        expediente_id = data.get('expediente_id')
        solicitud_id = data.get('solicitud_id')
        beneficios = data.get('beneficios', [])  # Array de {codigo, nombre, monto}
        total = data.get('total')
        
        if not expediente_id or not beneficios or not total:
            return jsonify({'error': 'Datos incompletos'}), 400
        
        cur = conn.cursor()
        funcionario_id = session.get('user_id')
        
        # Verificar estado de la solicitud para bloquear si está en pendiente
        if solicitud_id:
            cur.execute("""
                SELECT estado FROM app.solicitudes WHERE id = %s
            """, (solicitud_id,))
            solicitud_result = cur.fetchone()
            if solicitud_result and solicitud_result[0] == 'pendiente':
                return jsonify({
                    'error': 'No se puede calcular o recalcular el saldo insoluto de un expediente que está en revisión de jefatura. Debe estar rechazado para poder recalcular.'
                }), 400
        
        # Verificar si ya existe un cálculo activo (pendiente o aprobado)
        cur.execute("""
            SELECT id, estado FROM app.calculo_saldo_insoluto 
            WHERE expediente_id = %s AND estado IN ('pendiente', 'aprobado')
            ORDER BY fecha_calculo DESC LIMIT 1
        """, (expediente_id,))
        
        calculo_existente = cur.fetchone()
        if calculo_existente:
            # Verificar si el expediente está rechazado/enRevision para permitir modificar
            cur.execute("""
                SELECT estado FROM app.solicitudes 
                WHERE expediente_id = %s 
                ORDER BY id DESC LIMIT 1
            """, (expediente_id,))
            solicitud_estado = cur.fetchone()
            if not solicitud_estado or solicitud_estado[0] != 'rechazado/enRevision':
                return jsonify({
                    'error': f'Ya existe un cálculo {calculo_existente[1]} para este expediente. Solo se puede recalcular si el expediente fue rechazado.'
                }), 400
        
        # Si existe un cálculo rechazado y el expediente está en revisión, actualizar en lugar de crear nuevo
        calculo_id = None
        if calculo_existente:
            calculo_id = calculo_existente[0]
            # Actualizar cálculo existente
            cur.execute("""
                UPDATE app.calculo_saldo_insoluto 
                SET total_calculado = %s,
                    calculado_por = %s,
                    estado = 'pendiente',
                    fecha_calculo = NOW()
                WHERE id = %s
            """, (total, funcionario_id, calculo_id))
            
            # Eliminar detalles antiguos
            cur.execute("DELETE FROM app.detalle_calculo_saldo WHERE calculo_id = %s", (calculo_id,))
        else:
            # Insertar cálculo principal
            cur.execute("""
                INSERT INTO app.calculo_saldo_insoluto 
                (expediente_id, solicitud_id, total_calculado, calculado_por, estado)
                VALUES (%s, %s, %s, %s, 'pendiente')
                RETURNING id
            """, (expediente_id, solicitud_id, total, funcionario_id))
            calculo_id = cur.fetchone()[0]
        
        # Insertar detalles de beneficios (tanto para nuevo como para actualizado)
        for beneficio in beneficios:
            cur.execute("""
                INSERT INTO app.detalle_calculo_saldo 
                (calculo_id, beneficio_codigo, beneficio_nombre, monto)
                VALUES (%s, %s, %s, %s)
            """, (calculo_id, beneficio.get('codigo'), beneficio.get('nombre'), beneficio.get('monto')))
        
        print(f"✅ Cálculo guardado: ID {calculo_id}, Total: {total}")
        
        # Verificar si la solicitud está lista para evaluación (todas las firmas + cálculo)
        # IMPORTANTE: Verificar DESPUÉS de insertar el cálculo para que lo encuentre
        estado_actualizado = False
        if solicitud_id:
            print(f"\n{'='*60}")
            print(f"🔍 INICIANDO VERIFICACIÓN DE ESTADO PARA SOLICITUD {solicitud_id}")
            print(f"{'='*60}\n")
            resultado_verificacion = verificar_y_actualizar_estado_pendiente(expediente_id, solicitud_id, cur, conn)
            print(f"\n{'='*60}")
            if resultado_verificacion:
                print(f"✅ RESULTADO: Solicitud {solicitud_id} BLOQUEADA - Estado actualizado a 'pendiente'")
                estado_actualizado = True
            else:
                print(f"❌ RESULTADO: Solicitud {solicitud_id} NO se pudo actualizar a 'pendiente'")
                print(f"   Revisa los mensajes anteriores para ver qué condición no se cumplió")
            print(f"{'='*60}\n")
        else:
            print(f"⚠️ No se proporcionó solicitud_id, no se puede verificar estado")
        
        conn.commit()
        cur.close()
        conn.close()
        
        return jsonify({
            'success': True,
            'message': 'Cálculo guardado exitosamente',
            'data': {
                'calculo_id': calculo_id,
                'expediente_id': expediente_id,
                'total': total,
                'estado_actualizado': estado_actualizado
            }
        }), 201
        
    except Exception as e:
        print(f'❌ Error guardando cálculo: {e}')
        if 'conn' in locals():
            conn.rollback()
            conn.close()
        return jsonify({'error': f'Error interno del servidor: {str(e)}'}), 500

@app.route('/api/expediente/<int:expediente_id>/calculo-existente', methods=['GET'])
@login_required
def verificar_calculo_existente(expediente_id):
    """Verificar si existe un cálculo activo para un expediente"""
    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Error de conexión a la base de datos'}), 500
    
    try:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        # Buscar cálculo activo (pendiente o aprobado)
        cur.execute("""
            SELECT id, estado, total_calculado, fecha_calculo 
            FROM app.calculo_saldo_insoluto 
            WHERE expediente_id = %s AND estado IN ('pendiente', 'aprobado')
            ORDER BY fecha_calculo DESC LIMIT 1
        """, (expediente_id,))
        
        calculo = cur.fetchone()
        
        cur.close()
        conn.close()
        
        if calculo:
            return jsonify({
                'existe': True,
                'calculo': {
                    'id': calculo['id'],
                    'estado': calculo['estado'],
                    'total_calculado': float(calculo['total_calculado']),
                    'fecha_calculo': calculo['fecha_calculo'].isoformat() if calculo['fecha_calculo'] else None
                }
            }), 200
        else:
            return jsonify({
                'existe': False
            }), 200
        
    except Exception as e:
        print(f'❌ Error verificando cálculo: {e}')
        if 'conn' in locals():
            conn.close()
        return jsonify({'error': f'Error interno del servidor: {str(e)}'}), 500

@app.route('/api/expediente/<int:expediente_id>/calculo-completo', methods=['GET'])
@login_required
def obtener_calculo_completo(expediente_id):
    """Obtener cálculo completo de saldo insoluto con detalles de beneficios"""
    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Error de conexión a la base de datos'}), 500
    
    try:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        # Buscar cálculo activo (pendiente o aprobado)
        cur.execute("""
            SELECT 
                c.id,
                c.estado,
                c.total_calculado,
                c.fecha_calculo,
                c.solicitud_id,
                c.calculado_por,
                f.nombres || ' ' || f.apellido_p as funcionario_nombre
            FROM app.calculo_saldo_insoluto c
            LEFT JOIN app.funcionarios f ON c.calculado_por = f.id
            WHERE c.expediente_id = %s AND c.estado IN ('pendiente', 'aprobado')
            ORDER BY c.fecha_calculo DESC LIMIT 1
        """, (expediente_id,))
        
        calculo = cur.fetchone()
        
        if not calculo:
            cur.close()
            conn.close()
            return jsonify({
                'existe': False,
                'message': 'No existe cálculo para este expediente'
            }), 200
        
        # Obtener detalles de beneficios
        cur.execute("""
            SELECT 
                beneficio_codigo,
                beneficio_nombre,
                monto
            FROM app.detalle_calculo_saldo
            WHERE calculo_id = %s
            ORDER BY beneficio_codigo
        """, (calculo['id'],))
        
        detalles = cur.fetchall()
        
        cur.close()
        conn.close()
        
        return jsonify({
            'existe': True,
            'calculo': {
                'id': calculo['id'],
                'estado': calculo['estado'],
                'total_calculado': float(calculo['total_calculado']),
                'fecha_calculo': calculo['fecha_calculo'].isoformat() if calculo['fecha_calculo'] else None,
                'solicitud_id': calculo['solicitud_id'],
                'calculado_por': calculo['calculado_por'],
                'funcionario_nombre': calculo['funcionario_nombre'],
                'beneficios': [
                    {
                        'codigo': det['beneficio_codigo'],
                        'nombre': det['beneficio_nombre'],
                        'monto': float(det['monto'])
                    }
                    for det in detalles
                ]
            }
        }), 200
        
    except Exception as e:
        print(f'❌ Error obteniendo cálculo completo: {e}')
        if 'conn' in locals():
            conn.close()
        return jsonify({'error': f'Error interno del servidor: {str(e)}'}), 500

@app.route('/api/generar-resolucion/<int:expediente_id>', methods=['GET'])
@login_required
def generar_resolucion(expediente_id):
    """Generar resolución de saldo insoluto en formato Word"""
    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Error de conexión a la base de datos'}), 500
    
    try:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        # 1. Obtener datos del expediente, causante, representante y solicitud
        cur.execute("""
            SELECT 
                e.expediente_numero,
                e.fecha_creacion,
                c.fal_nombre,
                c.fal_apellido_p,
                c.fal_apellido_m,
                c.fal_run,
                c.fal_fecha_defuncion,
                c.fal_comuna_defuncion,
                r.rep_nombre,
                r.rep_apellido_p,
                r.rep_apellido_m,
                r.rep_rut,
                r.rep_calidad,
                s.folio,
                s.sucursal
            FROM app.expediente e
            JOIN app.causante c ON e.id = c.expediente_id
            LEFT JOIN app.representante r ON e.id = r.expediente_id
            JOIN app.solicitudes s ON e.id = s.expediente_id
            WHERE e.id = %s
            ORDER BY s.id DESC
            LIMIT 1
        """, (expediente_id,))
        
        datos_expediente = cur.fetchone()
        
        if not datos_expediente:
            cur.close()
            conn.close()
            return jsonify({'error': 'Expediente no encontrado'}), 404
        
        # 2. Obtener cálculo aprobado
        cur.execute("""
            SELECT 
                c.id,
                c.total_calculado,
                c.fecha_calculo,
                c.calculado_por,
                f.nombres,
                f.apellido_p,
                f.apellido_m
            FROM app.calculo_saldo_insoluto c
            LEFT JOIN app.funcionarios f ON c.calculado_por = f.id
            WHERE c.expediente_id = %s AND c.estado = 'aprobado'
            ORDER BY c.fecha_calculo DESC
            LIMIT 1
        """, (expediente_id,))
        
        calculo = cur.fetchone()
        
        if not calculo:
            cur.close()
            conn.close()
            return jsonify({'error': 'No existe un cálculo aprobado para este expediente'}), 400
        
        # 3. Obtener funcionario de jefatura que inició sesión (el que aprueba)
        funcionario_jefatura_id = session.get('user_id')
        if not funcionario_jefatura_id:
            cur.close()
            conn.close()
            return jsonify({'error': 'No se pudo identificar al funcionario de jefatura'}), 400
        
        cur.execute("""
            SELECT nombres, apellido_p, apellido_m
            FROM app.funcionarios
            WHERE id = %s
        """, (funcionario_jefatura_id,))
        
        funcionario_jefatura = cur.fetchone()
        if not funcionario_jefatura:
            cur.close()
            conn.close()
            return jsonify({'error': 'Funcionario de jefatura no encontrado'}), 404
        
        # 4. Preparar datos para el template
        nombre_causante = f"{datos_expediente['fal_nombre']} {datos_expediente['fal_apellido_p']} {datos_expediente['fal_apellido_m'] or ''}".strip()
        nombre_representante = f"{datos_expediente['rep_nombre'] or ''} {datos_expediente['rep_apellido_p'] or ''} {datos_expediente['rep_apellido_m'] or ''}".strip()
        nombre_funcionario_jefatura = f"{funcionario_jefatura['nombres'] or ''} {funcionario_jefatura['apellido_p'] or ''} {funcionario_jefatura['apellido_m'] or ''}".strip()
        
        # Generar número de resolución (usar folio o generar uno)
        numero_resolucion = datos_expediente['folio'] or f"RES-{expediente_id:03d}-{datetime.now().year}"
        
        # Contexto para el template
        context = {
            'NUMERO_CORRELATIVO': numero_resolucion,
            'FECHA_APROBACION': formatear_fecha(calculo['fecha_calculo']),
            'NOMBRE_CAUSANTE': nombre_causante,
            'RUT_CAUSANTE': formatear_rut(datos_expediente['fal_run']),
            'FECHA_FALLECIMIENTO': formatear_fecha(datos_expediente['fal_fecha_defuncion']),
            'NOMBRE_REPRESENTANTE': nombre_representante,
            'RUT_REPRESENTANTE': formatear_rut(datos_expediente['rep_rut']) if datos_expediente['rep_rut'] else '',
            'NOMBRE_FALLECIDA': nombre_causante,
            'VALOR_SALDO_INSOLUTO': formatear_moneda(calculo['total_calculado']),
            'FUNCIONARIO_JEFATURA': nombre_funcionario_jefatura,
            'FIRMA_FUNCIONARIO': nombre_funcionario_jefatura  # Funcionario de jefatura que inició sesión
        }
        
        # 5. Cargar template HTML y generar PDF directamente
        template_html_path = os.path.join(os.path.dirname(__file__), 'templates', 'resolucion_template.html')
        
        if not os.path.exists(template_html_path):
            cur.close()
            conn.close()
            return jsonify({'error': 'Template HTML de resolución no encontrado'}), 500
        
        # Leer el template HTML
        with open(template_html_path, 'r', encoding='utf-8') as f:
            html_template = f.read()
        
        # Renderizar el HTML con los datos usando Jinja2
        html_content = render_template_string(html_template, **context)
        
        # 6. Generar PDF directamente desde HTML usando xhtml2pdf
        try:
            pdf_output = io.BytesIO()
            
            # Generar PDF desde HTML
            pisa_status = pisa.CreatePDF(
                src=html_content,
                dest=pdf_output,
                encoding='utf-8'
            )
            
            if pisa_status.err:
                raise Exception(f'Error generando PDF: {pisa_status.err}')
            
            pdf_output.seek(0)
            
            # Verificar que el PDF se generó correctamente
            pdf_data = pdf_output.read()
            if not pdf_data.startswith(b'%PDF'):
                raise Exception('El archivo generado no es un PDF válido')
            
            pdf_output.seek(0)
            print('✅ PDF generado correctamente con xhtml2pdf')
            
            cur.close()
            conn.close()
            
            # Retornar el archivo PDF
            nombre_archivo = f"resolucion_{expediente_id}_{datetime.now().strftime('%Y%m%d')}.pdf"
            
            return send_file(
                pdf_output,
                mimetype='application/pdf',
                as_attachment=True,
                download_name=nombre_archivo
            )
            
        except Exception as pdf_error:
            print(f'❌ Error generando PDF con xhtml2pdf: {pdf_error}')
            import traceback
            traceback.print_exc()
            cur.close()
            conn.close()
            return jsonify({'error': f'Error generando PDF: {str(pdf_error)}'}), 500
        
    except Exception as e:
        print(f'❌ Error generando resolución: {e}')
        import traceback
        traceback.print_exc()
        if 'conn' in locals():
            conn.close()
        return jsonify({'error': f'Error interno del servidor: {str(e)}'}), 500

@app.route('/api/solicitudes/<int:solicitud_id>/aprobacion-items', methods=['GET'])
@login_required
def obtener_aprobacion_items(solicitud_id):
    """Obtener estado de aprobación de todos los items de una solicitud"""
    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Error de conexión a la base de datos'}), 500
    
    try:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        # Obtener expediente_id desde solicitud
        cur.execute("SELECT expediente_id FROM app.solicitudes WHERE id = %s", (solicitud_id,))
        solicitud = cur.fetchone()
        
        if not solicitud:
            cur.close()
            conn.close()
            return jsonify({'error': 'Solicitud no encontrada'}), 404
        
        expediente_id = solicitud['expediente_id']
        
        # Obtener todas las aprobaciones de items para esta solicitud
        cur.execute("""
            SELECT 
                item_tipo,
                estado,
                observacion,
                fecha_aprobacion,
                f.nombres || ' ' || f.apellido_p as aprobado_por_nombre
            FROM app.aprobacion_items ai
            LEFT JOIN app.funcionarios f ON ai.aprobado_por = f.id
            WHERE ai.expediente_id = %s AND ai.solicitud_id = %s
            ORDER BY item_tipo
        """, (expediente_id, solicitud_id))
        
        items = cur.fetchall()
        
        # Convertir a diccionario por tipo de item
        items_dict = {}
        for item in items:
            items_dict[item['item_tipo']] = {
                'estado': item['estado'],
                'observacion': item['observacion'],
                'fecha_aprobacion': item['fecha_aprobacion'].isoformat() if item['fecha_aprobacion'] else None,
                'aprobado_por': item['aprobado_por_nombre']
            }
        
        cur.close()
        conn.close()
        
        return jsonify({
            'success': True,
            'data': items_dict
        }), 200
        
    except Exception as e:
        print(f'❌ Error obteniendo aprobación de items: {e}')
        if 'conn' in locals():
            conn.close()
        return jsonify({'error': f'Error interno del servidor: {str(e)}'}), 500

@app.route('/api/solicitudes/<int:solicitud_id>/aprobacion-items', methods=['POST'])
@login_required
def aprobar_rechazar_item(solicitud_id):
    """Aprobar o rechazar un item específico de una solicitud"""
    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Error de conexión a la base de datos'}), 500
    
    try:
        data = request.get_json()
        item_tipo = data.get('item_tipo')
        estado = data.get('estado')  # 'aprobado' o 'rechazado'
        observacion = data.get('observacion', '')
        
        # Validaciones
        if not item_tipo:
            return jsonify({'error': 'item_tipo es requerido'}), 400
        
        if estado not in ['aprobado', 'rechazado']:
            return jsonify({'error': 'estado debe ser "aprobado" o "rechazado"'}), 400
        
        if estado == 'rechazado' and not observacion:
            return jsonify({'error': 'La observación es obligatoria al rechazar un item'}), 400
        
        if item_tipo not in ['causante', 'beneficiarios', 'firmas', 'calculo', 'documentos', 'general']:
            return jsonify({'error': 'item_tipo inválido'}), 400
        
        cur = conn.cursor()
        funcionario_id = session.get('user_id')
        
        # Obtener expediente_id desde solicitud
        cur.execute("SELECT expediente_id FROM app.solicitudes WHERE id = %s", (solicitud_id,))
        solicitud = cur.fetchone()
        
        if not solicitud:
            cur.close()
            conn.close()
            return jsonify({'error': 'Solicitud no encontrada'}), 404
        
        expediente_id = solicitud[0]
        
        # Insertar o actualizar aprobación del item
        cur.execute("""
            INSERT INTO app.aprobacion_items 
            (expediente_id, solicitud_id, item_tipo, estado, observacion, aprobado_por, fecha_aprobacion)
            VALUES (%s, %s, %s, %s, %s, %s, NOW())
            ON CONFLICT (expediente_id, solicitud_id, item_tipo) 
            DO UPDATE SET 
                estado = EXCLUDED.estado,
                observacion = EXCLUDED.observacion,
                aprobado_por = EXCLUDED.aprobado_por,
                fecha_aprobacion = NOW(),
                updated_at = NOW()
            RETURNING id
        """, (expediente_id, solicitud_id, item_tipo, estado, observacion if observacion else None, funcionario_id))
        
        aprobacion_id = cur.fetchone()[0]
        
        # Si se rechaza un item, cambiar estado de la solicitud a 'rechazado/enRevision'
        if estado == 'rechazado':
            # Verificar si hay otros items rechazados
            cur.execute("""
                SELECT COUNT(*) FROM app.aprobacion_items 
                WHERE expediente_id = %s AND solicitud_id = %s AND estado = 'rechazado'
            """, (expediente_id, solicitud_id))
            total_rechazados = cur.fetchone()[0]
            
            # Cambiar estado de solicitud a 'rechazado/enRevision' si hay al menos un item rechazado
            # Esto permite que el funcionario pueda editar y corregir
            # Si está en 'pendiente', cambiar a 'rechazado/enRevision'
            # Si ya está en 'rechazado/enRevision', mantenerlo
            cur.execute("""
                UPDATE app.solicitudes 
                SET estado = 'rechazado/enRevision'
                WHERE id = %s AND estado = 'pendiente'
            """, (solicitud_id,))
        
        conn.commit()
        cur.close()
        conn.close()
        
        return jsonify({
            'success': True,
            'message': f'Item {item_tipo} {estado} exitosamente',
            'data': {
                'id': aprobacion_id,
                'item_tipo': item_tipo,
                'estado': estado
            }
        }), 200
        
    except Exception as e:
        print(f'❌ Error aprobando/rechazando item: {e}')
        if 'conn' in locals():
            conn.rollback()
            conn.close()
        return jsonify({'error': f'Error interno del servidor: {str(e)}'}), 500

@app.route('/api/solicitudes-rechazadas', methods=['GET'])
@login_required
def solicitudes_rechazadas():
    """Obtener solicitudes rechazadas del funcionario actual"""
    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Error de conexión a la base de datos'}), 500
    
    try:
        funcionario_id = session.get('user_id')
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        # Obtener solicitudes rechazadas del funcionario (por expediente que gestionó)
        cur.execute("""
            SELECT DISTINCT
                e.id as expediente_id,
                e.expediente_numero,
                e.fecha_creacion,
                s.id as solicitud_id,
                s.folio,
                s.estado as estado_solicitud,
                s.firmado_funcionario,
                s.sucursal,
                c.fal_nombre || ' ' || c.fal_apellido_p || ' ' || COALESCE(c.fal_apellido_m, '') as causante_nombre_completo,
                c.fal_run as causante_rut,
                COUNT(DISTINCT ai.id) FILTER (WHERE ai.estado = 'rechazado') as items_rechazados
            FROM app.expediente e
            JOIN app.solicitudes s ON e.id = s.expediente_id
            JOIN app.causante c ON e.id = c.expediente_id
            LEFT JOIN app.aprobacion_items ai ON s.id = ai.solicitud_id AND ai.estado = 'rechazado'
            WHERE s.estado = 'rechazado/enRevision' AND e.funcionario_id = %s
            GROUP BY e.id, e.expediente_numero, e.fecha_creacion,
                     s.id, s.folio, s.estado, s.firmado_funcionario, s.sucursal,
                     c.fal_nombre, c.fal_apellido_p, c.fal_apellido_m, c.fal_run
            ORDER BY e.fecha_creacion DESC
        """, (funcionario_id,))
        
        solicitudes = cur.fetchall()
        
        resultados = []
        for s in solicitudes:
            resultados.append({
                'expediente_id': s['expediente_id'],
                'solicitud_id': s['solicitud_id'],
                'folio': s['folio'],
                'estado_solicitud': s['estado_solicitud'],
                'fecha_creacion': s['fecha_creacion'].isoformat() if s['fecha_creacion'] else None,
                'sucursal': s['sucursal'],
                'causante': {
                    'nombre_completo': s['causante_nombre_completo'],
                    'rut': s['causante_rut']
                },
                'items_rechazados': s['items_rechazados'] or 0
            })
        
        cur.close()
        conn.close()
        
        return jsonify({
            'success': True,
            'data': resultados
        }), 200
        
    except Exception as e:
        print(f'❌ Error obteniendo solicitudes rechazadas: {e}')
        if 'conn' in locals():
            conn.close()
        return jsonify({'error': f'Error interno del servidor: {str(e)}'}), 500

@app.route('/api/solicitudes/<int:solicitud_id>/aprobar', methods=['POST'])
@login_required
def aprobar_solicitud_completa(solicitud_id):
    """Aprobar una solicitud completa - verifica que todos los items estén aprobados"""
    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Error de conexión a la base de datos'}), 500
    
    try:
        cur = conn.cursor()
        funcionario_id = session.get('user_id')
        
        # Obtener expediente_id desde solicitud
        cur.execute("SELECT expediente_id, estado FROM app.solicitudes WHERE id = %s", (solicitud_id,))
        solicitud = cur.fetchone()
        
        if not solicitud:
            cur.close()
            conn.close()
            return jsonify({'error': 'Solicitud no encontrada'}), 404
        
        expediente_id = solicitud[0]
        estado_actual = solicitud[1]
        
        # Verificar que la solicitud no esté ya aprobada o rechazada
        if estado_actual == 'completado':
            cur.close()
            conn.close()
            return jsonify({'error': 'La solicitud ya está aprobada'}), 400
        
        # Permitir aprobar solicitudes en revisión (rechazado/enRevision)
        # Solo se pueden aprobar solicitudes en 'pendiente' o 'rechazado/enRevision'
        if estado_actual not in ['pendiente', 'rechazado/enRevision']:
            cur.close()
            conn.close()
            return jsonify({'error': f'No se puede aprobar una solicitud en estado: {estado_actual}. Debe estar en pendiente o rechazado/enRevision.'}), 400
        
        # Verificar que todos los items requeridos estén aprobados
        cur.execute("""
            SELECT item_tipo, estado 
            FROM app.aprobacion_items 
            WHERE expediente_id = %s AND solicitud_id = %s
        """, (expediente_id, solicitud_id))
        
        items = cur.fetchall()
        
        # Items requeridos que deben estar aprobados
        items_requeridos = ['causante', 'beneficiarios', 'firmas', 'calculo', 'documentos']
        items_aprobados = {item[0]: item[1] for item in items}
        
        # Verificar que todos los items requeridos estén aprobados
        items_faltantes = []
        for item_tipo in items_requeridos:
            if item_tipo not in items_aprobados or items_aprobados[item_tipo] != 'aprobado':
                items_faltantes.append(item_tipo)
        
        if items_faltantes:
            cur.close()
            conn.close()
            return jsonify({
                'error': f'Faltan items por aprobar: {", ".join(items_faltantes)}',
                'items_faltantes': items_faltantes
            }), 400
        
        # Cambiar estado de la solicitud a 'completado'
        cur.execute("""
            UPDATE app.solicitudes 
            SET estado = 'completado'
            WHERE id = %s
        """, (solicitud_id,))
        
        # Actualizar estado del cálculo a 'aprobado' si existe
        cur.execute("""
            UPDATE app.calculo_saldo_insoluto 
            SET estado = 'aprobado',
                updated_at = NOW()
            WHERE expediente_id = %s AND estado = 'pendiente'
        """, (expediente_id,))
        
        conn.commit()
        cur.close()
        conn.close()
        
        return jsonify({
            'success': True,
            'message': 'Solicitud aprobada exitosamente',
            'data': {
                'solicitud_id': solicitud_id,
                'estado': 'completado'
            }
        }), 200
        
    except Exception as e:
        print(f'❌ Error aprobando solicitud: {e}')
        if 'conn' in locals():
            conn.rollback()
            conn.close()
        return jsonify({'error': f'Error interno del servidor: {str(e)}'}), 500

@app.route('/api/solicitudes/<int:solicitud_id>/reenviar', methods=['POST'])
@login_required
def reenviar_solicitud(solicitud_id):
    """Reenviar solicitud rechazada para nueva evaluación por jefatura"""
    print(f"🔄 Petición de reenvío para solicitud: {solicitud_id}")
    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Error de conexión a la base de datos'}), 500
    
    try:
        cur = conn.cursor()
        
        # Verificar que la solicitud existe y está rechazada
        cur.execute("SELECT estado, expediente_id FROM app.solicitudes WHERE id = %s", (solicitud_id,))
        solicitud = cur.fetchone()
        
        if not solicitud:
            cur.close()
            conn.close()
            print(f"❌ Solicitud {solicitud_id} no encontrada")
            return jsonify({'error': 'Solicitud no encontrada'}), 404
        
        estado_actual = solicitud[0]
        expediente_id = solicitud[1]
        
        print(f"📊 Estado actual de solicitud {solicitud_id}: '{estado_actual}'")
        
        # Solo aceptar 'rechazado/enRevision' (estado cuando está siendo corregida)
        if estado_actual != 'rechazado/enRevision':
            cur.close()
            conn.close()
            print(f"⚠️ La solicitud no está en estado rechazado/enRevision. Estado: '{estado_actual}'")
            return jsonify({'error': f'La solicitud debe estar en estado rechazado/enRevision para reenviarla. Estado actual: {estado_actual}'}), 400
        
        # Cambiar estado de solicitud a 'pendiente'
        print(f"🔄 Cambiando estado de '{estado_actual}' a 'pendiente'...")
        cur.execute("""
            UPDATE app.solicitudes 
            SET estado = 'pendiente'
            WHERE id = %s
        """, (solicitud_id,))
        
        if cur.rowcount == 0:
            print(f"⚠️ No se pudo actualizar solicitud {solicitud_id} - rowcount: {cur.rowcount}")
        else:
            print(f"✅ Solicitud {solicitud_id} actualizada - rowcount: {cur.rowcount}")
        
        # Resetear items rechazados a 'pendiente' para nueva evaluación
        cur.execute("""
            UPDATE app.aprobacion_items 
            SET estado = 'pendiente',
                observacion = NULL,
                updated_at = NOW()
            WHERE expediente_id = %s AND solicitud_id = %s AND estado = 'rechazado'
        """, (expediente_id, solicitud_id))
        
        items_reseteados = cur.rowcount
        print(f"✅ Items rechazados reseteados: {items_reseteados}")
        
        # Mantener items aprobados como aprobados (no resetearlos)
        
        conn.commit()
        
        # Verificar que se guardó correctamente
        cur.execute("SELECT estado FROM app.solicitudes WHERE id = %s", (solicitud_id,))
        estado_verificado = cur.fetchone()[0]
        print(f"✅ Estado verificado después del commit: '{estado_verificado}'")
        
        cur.close()
        conn.close()
        
        return jsonify({
            'success': True,
            'message': 'Solicitud reenviada exitosamente para nueva evaluación',
            'data': {
                'solicitud_id': solicitud_id,
                'estado': 'pendiente',
                'estado_anterior': estado_actual,
                'items_reseteados': items_reseteados
            }
        }), 200
        
    except Exception as e:
        print(f'❌ Error reenviando solicitud: {e}')
        import traceback
        print(traceback.format_exc())
        if 'conn' in locals():
            conn.rollback()
            conn.close()
        return jsonify({'error': f'Error interno del servidor: {str(e)}'}), 500

@app.route('/api/solicitudes/<int:solicitud_id>/enviar', methods=['POST'])
@login_required
def enviar_solicitud_revision(solicitud_id):
    """Enviar solicitud rechazada a revisión (cambia de 'rechazado' a 'rechazado/enRevision')"""
    print(f"📤 Petición de envío a revisión para solicitud: {solicitud_id}")
    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Error de conexión a la base de datos'}), 500
    
    try:
        cur = conn.cursor()
        
        # Verificar que la solicitud existe y está rechazada
        cur.execute("SELECT estado, expediente_id FROM app.solicitudes WHERE id = %s", (solicitud_id,))
        solicitud = cur.fetchone()
        
        if not solicitud:
            cur.close()
            conn.close()
            print(f"❌ Solicitud {solicitud_id} no encontrada")
            return jsonify({'error': 'Solicitud no encontrada'}), 404
        
        estado_actual = solicitud[0]
        expediente_id = solicitud[1]
        
        print(f"📊 Estado actual de solicitud {solicitud_id}: '{estado_actual}'")
        
        # Solo aceptar 'rechazado' (no puede estar ya en revisión)
        if estado_actual != 'rechazado':
            cur.close()
            conn.close()
            print(f"⚠️ La solicitud no está en estado rechazado. Estado: '{estado_actual}'")
            return jsonify({'error': f'La solicitud debe estar rechazada para enviarla a revisión. Estado actual: {estado_actual}'}), 400
        
        # Cambiar estado de solicitud a 'rechazado/enRevision'
        print(f"🔄 Cambiando estado de 'rechazado' a 'rechazado/enRevision'...")
        cur.execute("""
            UPDATE app.solicitudes 
            SET estado = 'rechazado/enRevision'
            WHERE id = %s
        """, (solicitud_id,))
        
        if cur.rowcount == 0:
            print(f"⚠️ No se pudo actualizar solicitud {solicitud_id} - rowcount: {cur.rowcount}")
        else:
            print(f"✅ Solicitud {solicitud_id} actualizada - rowcount: {cur.rowcount}")
        
        # NO resetear items rechazados - mantener las observaciones para que jefatura vea qué se corrigió
        
        conn.commit()
        
        # Verificar que se guardó correctamente
        cur.execute("SELECT estado FROM app.solicitudes WHERE id = %s", (solicitud_id,))
        estado_verificado = cur.fetchone()[0]
        print(f"✅ Estado verificado después del commit: '{estado_verificado}'")
        
        cur.close()
        conn.close()
        
        return jsonify({
            'success': True,
            'message': 'Solicitud enviada a revisión exitosamente',
            'data': {
                'solicitud_id': solicitud_id,
                'estado': 'rechazado/enRevision',
                'estado_anterior': estado_actual
            }
        }), 200
        
    except Exception as e:
        print(f'❌ Error enviando solicitud a revisión: {e}')
        import traceback
        print(traceback.format_exc())
        if 'conn' in locals():
            conn.rollback()
            conn.close()
        return jsonify({'error': f'Error interno del servidor: {str(e)}'}), 500

# Registrar rutas de autocompletado (fuera de if __name__ para que se registren siempre)
try:
    from routes.autocompletar import register_routes as register_autocompletar_routes
    register_autocompletar_routes(app)
    print('✅ Rutas de autocompletado registradas')
except Exception as e:
    print(f'⚠️ Error registrando rutas de autocompletado: {e}')

if __name__ == '__main__':
    if test_connection():
        # Crear tabla de firmas de beneficiarios si no existe
        create_firmas_beneficiarios_table()
        # Crear tablas de cálculo de saldo insoluto si no existen
        from utils.database import create_calculo_saldo_insoluto_tables, create_aprobacion_items_table
        create_calculo_saldo_insoluto_tables()
        # Crear tabla de aprobación de items si no existe
        create_aprobacion_items_table()
        # Agregar columnas de firma de funcionario a solicitudes
        from utils.database import add_firma_funcionario_columns
        add_firma_funcionario_columns()
        # Aumentar tamaño de columnas de RUT
        from utils.database import fix_rut_columns
        fix_rut_columns()
        # Eliminar columnas innecesarias de firma
        from utils.database import remove_unused_firma_columns
        remove_unused_firma_columns()
        
        # Cargar Excel al iniciar
        from utils.excel_service import cargar_excel
        cargar_excel()
        
        config = Config()
        print(f'✅ Servidor Flask ejecutándose en puerto {config.PORT}')
        print(f'🔗 URL: http://localhost:{config.PORT}')
        app.run(host=config.HOST, port=config.PORT, debug=config.DEBUG)
    else:
        print('❌ No se pudo conectar a la base de datos')
