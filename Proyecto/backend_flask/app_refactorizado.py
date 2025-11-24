"""
Aplicación Flask principal - Solo inicialización y registro de rutas
"""
from flask import Flask
from flask_cors import CORS
from flask_session import Session
import os
from config import Config
from werkzeug.sansio.response import Response

# Parche para compatibilidad entre Flask-Session y Werkzeug 3.x
original_set_cookie = Response.set_cookie

def patched_set_cookie(self, key, value='', max_age=None, expires=None, 
                       path='/', domain=None, secure=False, httponly=False, 
                       samesite=None, charset='utf-8'):
    """Parche para convertir value de bytes a string si es necesario"""
    if isinstance(value, bytes):
        value = value.decode('utf-8')
    return original_set_cookie(self, key, value, max_age, expires, path, 
                                domain, secure, httponly, samesite, charset)

# Aplicar el parche
Response.set_cookie = patched_set_cookie

# Crear aplicación Flask
app = Flask(__name__)

# Configurar CORS
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
app.config.from_object(Config)

# Inicializar Flask-Session
Session(app)

# Registrar todas las rutas
print('📦 Registrando rutas...')

# Rutas de autenticación
from routes import auth
auth.register_routes(app)
print('✅ Rutas de autenticación registradas')

# Rutas de solicitudes
from routes import solicitudes
solicitudes.register_routes(app)
print('✅ Rutas de solicitudes registradas')

# Rutas de documentos
from routes import documentos
documentos.register_routes(app)
print('✅ Rutas de documentos registradas')

# Rutas de expedientes
from routes import expedientes
expedientes.register_routes(app)
print('✅ Rutas de expedientes registradas')

# Rutas de usuarios
from routes import usuarios
usuarios.register_routes(app)
print('✅ Rutas de usuarios registradas')

# Rutas de health
from routes import health
health.register_routes(app)
print('✅ Rutas de health registradas')

# Rutas de autocompletado
try:
    from routes import autocompletar
    autocompletar.register_routes(app)
    print('✅ Rutas de autocompletado registradas')
except Exception as e:
    print(f'⚠️ Error registrando rutas de autocompletado: {e}')

# Rutas de validación
try:
    from routes import validacion
    validacion.register_routes(app)
    print('✅ Rutas de validación registradas')
except Exception as e:
    print(f'⚠️ Error registrando rutas de validación: {e}')

# Rutas de archivos estáticos (deben ir al final)
from routes import static
static.register_routes(app)
print('✅ Rutas de archivos estáticos registradas')

print('✅ Todas las rutas registradas correctamente')

# Inicialización de base de datos
if __name__ == '__main__':
    from utils.database import test_connection, create_firmas_beneficiarios_table
    from utils.excel_service import cargar_excel
    
    if test_connection():
        # Crear tabla de firmas de beneficiarios si no existe
        create_firmas_beneficiarios_table()
        
        # Crear tablas de cálculo de saldo insoluto si no existen
        from utils.database import (
            create_calculo_saldo_insoluto_tables, 
            create_aprobacion_items_table,
            add_firma_funcionario_columns,
            fix_rut_columns,
            remove_unused_firma_columns
        )
        create_calculo_saldo_insoluto_tables()
        create_aprobacion_items_table()
        add_firma_funcionario_columns()
        fix_rut_columns()
        remove_unused_firma_columns()
        
        # Cargar Excel al iniciar
        cargar_excel()
        
        config = Config()
        print(f'✅ Servidor Flask ejecutándose en puerto {config.PORT}')
        print(f'🔗 URL: http://localhost:{config.PORT}')
        app.run(host=config.HOST, port=config.PORT, debug=config.DEBUG)
    else:
        print('❌ No se pudo conectar a la base de datos')

