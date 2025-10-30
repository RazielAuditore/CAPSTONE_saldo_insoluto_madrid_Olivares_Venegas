"""
Rutas de salud del sistema
"""
from flask import jsonify
from datetime import datetime

def register_routes(app):
    """Registrar rutas de health check"""
    
    @app.route('/api/health', methods=['GET'])
    def health_check():
        """Endpoint de salud del servidor"""
        return jsonify({
            'status': 'OK',
            'message': 'Servidor Flask funcionando correctamente',
            'timestamp': datetime.now().isoformat()
        }), 200


