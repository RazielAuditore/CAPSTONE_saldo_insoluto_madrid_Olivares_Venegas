"""
Rutas de gestión de usuarios
"""
from flask import request, jsonify, session
from psycopg2.extras import RealDictCursor
from utils.database import get_db_connection
from utils.helpers import validar_rut_chileno, hash_password
import re

def register_routes(app):
    """Registrar rutas de usuarios"""
    
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


