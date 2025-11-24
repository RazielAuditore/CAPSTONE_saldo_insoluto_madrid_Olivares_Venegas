"""
Rutas de autenticación
"""
from flask import request, jsonify, session
import bcrypt
from utils.database import get_db_connection
from psycopg2.extras import RealDictCursor
from middleware.auth import login_required

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
        import traceback
        try:
            print('🔔 Petición de cierre de sesión recibida')
            print(f'📋 Tipo de session: {type(session)}')
            
            # Intentar obtener las keys de la sesión de forma segura
            try:
                session_keys = list(session.keys()) if hasattr(session, 'keys') else []
                print(f'📋 Session keys antes de limpiar: {session_keys}')
            except Exception as session_error:
                print(f'⚠️ No se pudieron leer las keys de la sesión: {session_error}')
                print(f'⚠️ Traceback: {traceback.format_exc()}')
                session_keys = []
            
            # Limpiar la sesión de forma segura
            try:
                if hasattr(session, 'clear'):
                    session.clear()
                    print('✅ Sesión limpiada exitosamente')
                else:
                    print('⚠️ session no tiene método clear')
                    # Intentar limpiar manualmente
                    for key in list(session.keys()):
                        session.pop(key, None)
            except Exception as clear_error:
                print(f'⚠️ Error al limpiar sesión: {clear_error}')
                print(f'⚠️ Traceback: {traceback.format_exc()}')
                # Continuar de todas formas
            
            return jsonify({
                'success': True,
                'message': 'Sesión cerrada exitosamente'
            }), 200
            
        except Exception as e:
            print(f'❌ Error cerrando sesión: {e}')
            print(f'❌ Traceback completo:')
            traceback.print_exc()
            
            # Intentar limpiar la sesión de todas formas
            try:
                if hasattr(session, 'clear'):
                    session.clear()
                else:
                    for key in list(session.keys()):
                        session.pop(key, None)
            except:
                pass
            
            # Devolver error pero con información útil
            return jsonify({
                'success': False,
                'error': str(e),
                'message': 'Error al cerrar sesión',
                'traceback': traceback.format_exc()
            }), 500

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
            # Devolver 200 con authenticated: False (no es un error, simplemente no hay sesión)
            return jsonify({'authenticated': False}), 200
