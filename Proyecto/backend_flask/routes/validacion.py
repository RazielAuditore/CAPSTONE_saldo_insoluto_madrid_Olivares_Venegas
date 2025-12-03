"""
Rutas de validación y firmas
"""
from flask import request, jsonify, session
import bcrypt
from psycopg2.extras import RealDictCursor
from utils.database import get_db_connection
from middleware.auth import login_required

def register_routes(app):
    """Registrar rutas de validación"""
    
    # Rutas movidas a routes/firmas.py para evitar duplicación
    # Las funciones firmar_beneficiario y obtener_firmas_beneficiarios ahora están en routes/firmas.py

    @app.route('/api/validar-clave-funcionario', methods=['POST'])
    @login_required
    def validar_clave_funcionario():
        """Validar la clave del funcionario logueado"""
        data = request.get_json()
        password = data.get('password')
        
        if not password:
            return jsonify({'error': 'Contraseña requerida'}), 400
        
        conn = get_db_connection()
        if not conn:
            return jsonify({'error': 'Error de conexión a la base de datos'}), 500
        
        try:
            cur = conn.cursor(cursor_factory=RealDictCursor)
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
                return jsonify({'valid': False, 'error': 'Contraseña incorrecta'}), 200
                
        except Exception as e:
            if 'conn' in locals():
                conn.close()
            return jsonify({'error': f'Error interno del servidor: {str(e)}'}), 500


