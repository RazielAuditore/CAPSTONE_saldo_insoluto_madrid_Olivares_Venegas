"""
Aplicación Flask principal para el sistema de Saldo Insoluto
"""
from flask import Flask, send_from_directory
from flask_cors import CORS 
from flask_session import Session
import os
from config import Config
from utils.database import test_connection, create_firmas_beneficiarios_table

# Aplicar parche de compatibilidad para Flask-Session y Werkzeug 3.x
from utils.werkzeug_patch import apply_patch
apply_patch()

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

# Registrar todas las rutas
def register_all_routes():
    """Registrar todas las rutas desde los módulos de forma automática"""
    # Diccionario con todas las rutas a registrar
    # El orden importa: static debe ir al final
    routes_config = [
        ('routes.auth', 'autenticación'),
        ('routes.solicitudes', 'solicitudes'),
        ('routes.expedientes', 'expedientes'),
        ('routes.documentos', 'documentos'),
        ('routes.usuarios', 'usuarios'),
        ('routes.health', 'health check'),
        ('routes.validacion', 'validación'),
        ('routes.firmas', 'firmas'),
        ('routes.busqueda', 'búsqueda'),
        ('routes.calculos', 'cálculos'),
        ('routes.resoluciones', 'resoluciones'),
        ('routes.aprobaciones', 'aprobaciones'),
        ('routes.autocompletar', 'autocompletado'),
        ('routes.static', 'archivos estáticos'),  # Debe ir al final
    ]
    
    for module_path, route_name in routes_config:
        try:
            module = __import__(module_path, fromlist=['register_routes'])
            register_function = getattr(module, 'register_routes')
            register_function(app)
            print(f'✅ Rutas de {route_name} registradas')
        except ImportError as e:
            print(f'⚠️ Error importando módulo {module_path}: {e}')
        except AttributeError as e:
            print(f'⚠️ Error: {module_path} no tiene función register_routes: {e}')
        except Exception as e:
            print(f'⚠️ Error registrando rutas de {route_name}: {e}')

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
