"""
Aplicación Flask principal para el sistema de Saldo Insoluto
"""
from flask import Flask, send_from_directory
from flask_cors import CORS 
from flask_session import Session
import os
from config import Config
from utils.database import test_connection, create_firmas_beneficiarios_table

# Parche para compatibilidad entre Flask-Session y Werkzeug 3.x
from werkzeug.sansio.response import Response
original_set_cookie = Response.set_cookie

def patched_set_cookie(self, *args, **kwargs):
    """Parche para convertir value de bytes a string si es necesario"""
    # Convertir value de bytes a string si es necesario
    if len(args) > 1 and isinstance(args[1], bytes):
        args = (args[0], args[1].decode('utf-8'), *args[2:])
    elif 'value' in kwargs and isinstance(kwargs['value'], bytes):
        kwargs['value'] = kwargs['value'].decode('utf-8')
    
    # Llamar a la función original con todos los argumentos
    return original_set_cookie(self, *args, **kwargs)

# Aplicar el parche
Response.set_cookie = patched_set_cookie

# Crear aplicación Flask
app = Flask(__name__)

# Configurar CORS
CORS(app, supports_credentials=True, origins=[
    'http://localhost:3001',
    'http://localhost:8000',
    'http://localhost:8080',
    'http://127.0.0.1:3001',
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

# Configuración de la aplicación
app.config.from_object(Config)

# Inicializar Flask-Session
Session(app)

# Configurar ruta base para archivos estáticos (directorio Proyecto/)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Registrar todas las rutas
def register_all_routes():
    """Registrar todas las rutas desde los módulos"""
    try:
        # Rutas de autenticación
        from routes.auth import register_routes as register_auth_routes
        register_auth_routes(app)
        print('✅ Rutas de autenticación registradas')
    except Exception as e:
        print(f'⚠️ Error registrando rutas de autenticación: {e}')

    try:
        # Rutas de solicitudes
        from routes.solicitudes import register_routes as register_solicitudes_routes
        register_solicitudes_routes(app)
        print('✅ Rutas de solicitudes registradas')
    except Exception as e:
        print(f'⚠️ Error registrando rutas de solicitudes: {e}')

    try:
        # Rutas de expedientes
        from routes.expedientes import register_routes as register_expedientes_routes
        register_expedientes_routes(app)
        print('✅ Rutas de expedientes registradas')
    except Exception as e:
        print(f'⚠️ Error registrando rutas de expedientes: {e}')

    try:
        # Rutas de documentos
        from routes.documentos import register_routes as register_documentos_routes
        register_documentos_routes(app)
        print('✅ Rutas de documentos registradas')
    except Exception as e:
        print(f'⚠️ Error registrando rutas de documentos: {e}')

    try:
        # Rutas de usuarios
        from routes.usuarios import register_routes as register_usuarios_routes
        register_usuarios_routes(app)
        print('✅ Rutas de usuarios registradas')
    except Exception as e:
        print(f'⚠️ Error registrando rutas de usuarios: {e}')

    try:
        # Rutas de health check
        from routes.health import register_routes as register_health_routes
        register_health_routes(app)
        print('✅ Rutas de health check registradas')
    except Exception as e:
        print(f'⚠️ Error registrando rutas de health check: {e}')

    try:
        # Rutas de validación
        from routes.validacion import register_routes as register_validacion_routes
        register_validacion_routes(app)
        print('✅ Rutas de validación registradas')
    except Exception as e:
        print(f'⚠️ Error registrando rutas de validación: {e}')

    try:
        # Rutas de firmas
        from routes.firmas import register_routes as register_firmas_routes
        register_firmas_routes(app)
        print('✅ Rutas de firmas registradas')
    except Exception as e:
        print(f'⚠️ Error registrando rutas de firmas: {e}')

    try:
        # Rutas de búsqueda
        from routes.busqueda import register_routes as register_busqueda_routes
        register_busqueda_routes(app)
        print('✅ Rutas de búsqueda registradas')
    except Exception as e:
        print(f'⚠️ Error registrando rutas de búsqueda: {e}')

    try:
        # Rutas de cálculos
        from routes.calculos import register_routes as register_calculos_routes
        register_calculos_routes(app)
        print('✅ Rutas de cálculos registradas')
    except Exception as e:
        print(f'⚠️ Error registrando rutas de cálculos: {e}')

    try:
        # Rutas de resoluciones
        from routes.resoluciones import register_routes as register_resoluciones_routes
        register_resoluciones_routes(app)
        print('✅ Rutas de resoluciones registradas')
    except Exception as e:
        print(f'⚠️ Error registrando rutas de resoluciones: {e}')

    try:
        # Rutas de aprobaciones
        from routes.aprobaciones import register_routes as register_aprobaciones_routes
        register_aprobaciones_routes(app)
        print('✅ Rutas de aprobaciones registradas')
    except Exception as e:
        print(f'⚠️ Error registrando rutas de aprobaciones: {e}')

    try:
        # Rutas de autocompletado
        from routes.autocompletar import register_routes as register_autocompletar_routes
        register_autocompletar_routes(app)
        print('✅ Rutas de autocompletado registradas')
    except Exception as e:
        print(f'⚠️ Error registrando rutas de autocompletado: {e}')

    try:
        # Rutas de archivos estáticos (debe ir al final)
        from routes.static import register_routes as register_static_routes
        register_static_routes(app)
        print('✅ Rutas de archivos estáticos registradas')
    except Exception as e:
        print(f'⚠️ Error registrando rutas de archivos estáticos: {e}')

# Registrar todas las rutas
register_all_routes()

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
