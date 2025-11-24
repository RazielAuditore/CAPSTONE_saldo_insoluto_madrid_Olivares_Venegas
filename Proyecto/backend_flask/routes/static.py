"""
Rutas para servir archivos estáticos
"""
import os
from flask import send_from_directory, jsonify

def register_routes(app):
    """Registrar rutas de archivos estáticos"""
    # Configurar ruta base para archivos estáticos (directorio Proyecto/)
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    
    @app.route('/')
    def index():
        """Servir la página principal index.html"""
        return send_from_directory(BASE_DIR, 'index.html')
    
    @app.route('/<path:filename>')
    def serve_static(filename):
        """Servir archivos estáticos HTML, CSS, JS, imágenes, etc."""
        # Excluir rutas de API
        if filename.startswith('api/'):
            return jsonify({'error': 'Ruta de API no encontrada'}), 404
        
        # Solo servir archivos con extensiones permitidas
        allowed_extensions = ['.html', '.css', '.js', '.png', '.jpg', '.jpeg', '.svg', '.gif', '.ico', '.txt']
        if any(filename.lower().endswith(ext) for ext in allowed_extensions):
            try:
                return send_from_directory(BASE_DIR, filename)
            except Exception as e:
                return jsonify({'error': f'Archivo no encontrado: {str(e)}'}), 404
        else:
            return jsonify({'error': 'Archivo no encontrado'}), 404

