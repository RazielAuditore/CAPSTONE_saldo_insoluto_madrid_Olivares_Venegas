"""
Rutas de validación y firmas
"""
from flask import request, jsonify, session
import bcrypt
from psycopg2.extras import RealDictCursor
from utils.database import get_db_connection
from routes.auth import login_required

def register_routes(app):
    """Registrar rutas de validación"""
    
    @app.route('/api/beneficiarios/<int:beneficiario_id>/firma', methods=['POST'])
    @login_required
    def firmar_beneficiario(beneficiario_id):
        """Firmar como beneficiario usando contraseña de app externa"""
        conn = get_db_connection()
        if not conn:
            return jsonify({'error': 'Error de conexión a la base de datos'}), 500
        
        try:
            data = request.get_json()
            
            if not data.get('firma_hash'):
                return jsonify({'error': 'Firma (contraseña) es requerida'}), 400
            
            if not data.get('expediente_id'):
                return jsonify({'error': 'ID de expediente es requerido'}), 400
            
            firma_hash = data['firma_hash']
            expediente_id = data['expediente_id']
            
            cur = conn.cursor()
            
            cur.execute("""
                SELECT id, ben_nombre, ben_run 
                FROM app.beneficiarios 
                WHERE id = %s AND expediente_id = %s
            """, (beneficiario_id, expediente_id))
            
            beneficiario = cur.fetchone()
            if not beneficiario:
                return jsonify({'error': 'Beneficiario no encontrado'}), 404
            
            # Verificar si ya tiene una firma activa en usuarios_firma
            cur.execute("""
                SELECT uf.id FROM app.usuarios_firma uf
                JOIN app.beneficiarios b ON uf.rut = b.ben_run
                WHERE b.id = %s AND b.expediente_id = %s
            """, (beneficiario_id, expediente_id))
            
            if cur.fetchone():
                return jsonify({'error': 'El beneficiario ya tiene una firma activa'}), 400
            
            cur.execute("""
                SELECT uf.id FROM app.usuarios_firma uf
                JOIN app.beneficiarios b ON uf.rut = b.ben_run
                WHERE b.id = %s AND b.expediente_id = %s
            """, (beneficiario_id, expediente_id))
            
            firma_result = cur.fetchone()
            firma_id = firma_result[0] if firma_result else None
            
            conn.commit()
            cur.close()
            conn.close()
            
            return jsonify({
                'success': True,
                'message': 'Firma de beneficiario verificada exitosamente',
                'data': {
                    'firma_id': firma_id,
                    'beneficiario_id': beneficiario_id,
                    'expediente_id': expediente_id,
                    'beneficiario': {'nombre': beneficiario[1], 'rut': beneficiario[2]}
                }
            }), 200
            
        except Exception as e:
            if 'conn' in locals():
                conn.rollback()
                conn.close()
            return jsonify({'error': f'Error interno del servidor: {str(e)}'}), 500

    @app.route('/api/expediente/<int:expediente_id>/firmas-beneficiarios', methods=['GET'])
    @login_required
    def obtener_firmas_beneficiarios(expediente_id):
        """Obtener todas las firmas de beneficiarios de un expediente"""
        conn = get_db_connection()
        if not conn:
            return jsonify({'error': 'Error de conexión a la base de datos'}), 500
        
        try:
            cur = conn.cursor(cursor_factory=RealDictCursor)
            
            cur.execute("""
                SELECT uf.id as firma_id, uf.rut, b.id as beneficiario_id, b.ben_nombre, b.ben_run
                FROM app.usuarios_firma uf
                JOIN app.beneficiarios b ON uf.rut = b.ben_run
                WHERE b.expediente_id = %s
                ORDER BY uf.id DESC
            """, (expediente_id,))
            
            firmas = cur.fetchall()
            
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
            if 'conn' in locals():
                conn.close()
            return jsonify({'error': f'Error interno del servidor: {str(e)}'}), 500

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


