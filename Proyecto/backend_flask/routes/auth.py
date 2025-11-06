"""
Rutas de autenticación
"""
from flask import request, jsonify, session
from functools import wraps
import bcrypt
from utils.database import get_db_connection
from psycopg2.extras import RealDictCursor

# Exportar login_required para uso en otros módulos
def login_required(f):
    """Decorador para requerir autenticación"""
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

def register_routes(app):
    """Registrar rutas de autenticación"""
    
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

