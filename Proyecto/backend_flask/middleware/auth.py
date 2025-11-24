"""
Decoradores de autenticación y autorización
"""
from functools import wraps
from flask import jsonify, session

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

