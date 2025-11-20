"""
Rutas para autocompletar formularios desde Excel
"""
from flask import request, jsonify
from utils.excel_service import (
    buscar_representante, 
    buscar_causante, 
    buscar_beneficiarios,
    buscar_beneficiario_por_rut,
    recargar_excel,
    esta_cargado,
    normalizar_rut
)

def register_routes(app):
    """Registrar rutas de autocompletado"""
    
    @app.route('/api/autocompletar/representante/<rut>', methods=['GET'])
    def autocompletar_representante(rut):
        """Obtener datos del representante por RUT"""
        try:
            # Normalizar RUT
            rut_norm = normalizar_rut(rut)
            
            if not rut_norm:
                return jsonify({'error': 'RUT no válido'}), 400
            
            # Buscar representante
            datos = buscar_representante(rut_norm)
            
            if datos is None:
                return jsonify({'error': 'Representante no encontrado'}), 404
            
            return jsonify({'data': datos}), 200
            
        except Exception as e:
            print(f'❌ Error en autocompletar_representante: {str(e)}')
            return jsonify({'error': f'Error interno: {str(e)}'}), 500
    
    @app.route('/api/autocompletar/causante/<rut>', methods=['GET'])
    def autocompletar_causante(rut):
        """Obtener datos del causante por RUT"""
        try:
            # Normalizar RUT
            rut_norm = normalizar_rut(rut)
            
            if not rut_norm:
                return jsonify({'error': 'RUT no válido'}), 400
            
            # Buscar causante
            datos = buscar_causante(rut_norm)
            
            if datos is None:
                return jsonify({'error': 'Causante no encontrado'}), 404
            
            return jsonify({'data': datos}), 200
            
        except Exception as e:
            print(f'❌ Error en autocompletar_causante: {str(e)}')
            return jsonify({'error': f'Error interno: {str(e)}'}), 500
    
    @app.route('/api/autocompletar/beneficiarios/<rut_causante>', methods=['GET'])
    def autocompletar_beneficiarios(rut_causante):
        """Obtener beneficiarios por RUT del causante"""
        try:
            # Normalizar RUT
            rut_norm = normalizar_rut(rut_causante)
            
            if not rut_norm:
                return jsonify({'error': 'RUT no válido'}), 400
            
            # Buscar beneficiarios
            beneficiarios = buscar_beneficiarios(rut_norm)
            
            return jsonify({'data': beneficiarios}), 200
            
        except Exception as e:
            print(f'❌ Error en autocompletar_beneficiarios: {str(e)}')
            return jsonify({'error': f'Error interno: {str(e)}'}), 500
    
    @app.route('/api/autocompletar/recargar', methods=['POST'])
    def recargar_excel_endpoint():
        """Recargar archivos Excel (útil después de actualizarlos)"""
        try:
            if recargar_excel():
                return jsonify({'message': 'Excel recargados exitosamente'}), 200
            else:
                return jsonify({'error': 'Error al recargar Excel'}), 500
        except Exception as e:
            print(f'❌ Error recargando Excel: {str(e)}')
            return jsonify({'error': f'Error interno: {str(e)}'}), 500
    
    @app.route('/api/autocompletar/beneficiario/<rut>', methods=['GET'])
    def autocompletar_beneficiario(rut):
        """Obtener nombre del beneficiario por su RUT (solo nombre)"""
        try:
            # Normalizar RUT
            rut_norm = normalizar_rut(rut)
            
            if not rut_norm:
                return jsonify({'error': 'RUT no válido'}), 400
            
            # Buscar beneficiario
            datos = buscar_beneficiario_por_rut(rut_norm)
            
            if datos is None:
                return jsonify({'error': 'Beneficiario no encontrado'}), 404
            
            return jsonify({'data': datos}), 200
            
        except Exception as e:
            print(f'❌ Error en autocompletar_beneficiario: {str(e)}')
            return jsonify({'error': f'Error interno: {str(e)}'}), 500
    
    @app.route('/api/autocompletar/status', methods=['GET'])
    def status_excel():
        """Verificar estado de carga de Excel"""
        return jsonify({
            'cargado': esta_cargado()
        }), 200

