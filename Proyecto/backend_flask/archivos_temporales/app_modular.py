"""
Versión modularizada de app.py
Esta es una versión refactorizada que separa el código en módulos
"""
from flask import Flask, session
from flask_cors import CORS
from flask_session import Session
from datetime import datetime
from config import Config

# Importar módulos
from utils.database import get_db_connection, test_connection, create_firmas_beneficiarios_table
from utils.helpers import ALLOWED_EXTENSIONS, MAX_FILE_SIZE
from routes.auth import register_routes as register_auth_routes

app = Flask(__name__)
CORS(app, supports_credentials=True, origins=['http://localhost:8000'])

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

# Configuración de la aplicación
app.config.from_object(Config)

# Configurar CORS para permitir comunicación entre puertos
CORS(app, origins=['http://localhost:8080', 'http://127.0.0.1:8080'])

# Registrar todas las rutas
register_auth_routes(app)

from routes.documentos import register_routes as register_documentos_routes
from routes.usuarios import register_routes as register_usuarios_routes
from routes.solicitudes import register_routes as register_solicitudes_routes
from routes.expedientes import register_routes as register_expedientes_routes
from routes.validacion import register_routes as register_validacion_routes
from routes.health import register_routes as register_health_routes

register_documentos_routes(app)
register_usuarios_routes(app)
register_solicitudes_routes(app)
register_expedientes_routes(app)
register_validacion_routes(app)
register_health_routes(app)

if __name__ == '__main__':
    if test_connection():
        # Crear tabla de firmas de beneficiarios si no existe
        create_firmas_beneficiarios_table()
        
        config = Config()
        print(f'✅ Servidor Flask modularizado ejecutándose en puerto {config.PORT}')
        print(f'🔗 URL: http://localhost:{config.PORT}')
        print(f'⚠️  NOTA: Esta es una versión de prueba de la modularización')
        print(f'⚠️  El archivo app.py original sigue siendo el activo')
        app.run(host=config.HOST, port=config.PORT, debug=config.DEBUG)
    else:
        print('❌ No se pudo conectar a la base de datos')

