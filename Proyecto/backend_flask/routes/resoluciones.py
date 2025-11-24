"""
Rutas de generación de resoluciones
"""
from flask import request, jsonify, session, send_file, render_template_string
from datetime import datetime
import os
import io
from psycopg2.extras import RealDictCursor
from utils.database import get_db_connection
from utils.helpers import formatear_rut, formatear_fecha, formatear_moneda
from middleware.auth import login_required

# Importar xhtml2pdf si está disponible
try:
    from xhtml2pdf import pisa
    XHTML2PDF_AVAILABLE = True
except ImportError as e:
    print(f'⚠️ xhtml2pdf no disponible: {e}')
    XHTML2PDF_AVAILABLE = False
    pisa = None

def register_routes(app):
    """Registrar rutas de resoluciones"""
    
    @app.route('/api/generar-resolucion/<int:expediente_id>', methods=['GET'])
    @login_required
    def generar_resolucion(expediente_id):
        """Generar resolución de saldo insoluto en formato PDF"""
        conn = get_db_connection()
        if not conn:
            return jsonify({'error': 'Error de conexión a la base de datos'}), 500
        
        try:
            cur = conn.cursor(cursor_factory=RealDictCursor)
            
            # 1. Obtener datos del expediente, causante, representante y solicitud
            cur.execute("""
                SELECT 
                    e.expediente_numero,
                    e.fecha_creacion,
                    c.fal_nombre,
                    c.fal_apellido_p,
                    c.fal_apellido_m,
                    c.fal_run,
                    c.fal_fecha_defuncion,
                    c.fal_comuna_defuncion,
                    r.rep_nombre,
                    r.rep_apellido_p,
                    r.rep_apellido_m,
                    r.rep_rut,
                    r.rep_calidad,
                    s.folio,
                    s.sucursal
                FROM app.expediente e
                JOIN app.causante c ON e.id = c.expediente_id
                LEFT JOIN app.representante r ON e.id = r.expediente_id
                JOIN app.solicitudes s ON e.id = s.expediente_id
                WHERE e.id = %s
                ORDER BY s.id DESC
                LIMIT 1
            """, (expediente_id,))
            
            datos_expediente = cur.fetchone()
            
            if not datos_expediente:
                cur.close()
                conn.close()
                return jsonify({'error': 'Expediente no encontrado'}), 404
            
            # 2. Obtener cálculo aprobado
            cur.execute("""
                SELECT 
                    c.id,
                    c.total_calculado,
                    c.fecha_calculo,
                    c.calculado_por,
                    f.nombres,
                    f.apellido_p,
                    f.apellido_m
                FROM app.calculo_saldo_insoluto c
                LEFT JOIN app.funcionarios f ON c.calculado_por = f.id
                WHERE c.expediente_id = %s AND c.estado = 'aprobado'
                ORDER BY c.fecha_calculo DESC
                LIMIT 1
            """, (expediente_id,))
            
            calculo = cur.fetchone()
            
            if not calculo:
                cur.close()
                conn.close()
                return jsonify({'error': 'No existe un cálculo aprobado para este expediente'}), 400
            
            # 3. Obtener funcionario de jefatura que inició sesión (el que aprueba)
            funcionario_jefatura_id = session.get('user_id')
            if not funcionario_jefatura_id:
                cur.close()
                conn.close()
                return jsonify({'error': 'No se pudo identificar al funcionario de jefatura'}), 400
            
            cur.execute("""
                SELECT nombres, apellido_p, apellido_m
                FROM app.funcionarios
                WHERE id = %s
            """, (funcionario_jefatura_id,))
            
            funcionario_jefatura = cur.fetchone()
            if not funcionario_jefatura:
                cur.close()
                conn.close()
                return jsonify({'error': 'Funcionario de jefatura no encontrado'}), 404
            
            # 4. Preparar datos para el template
            nombre_causante = f"{datos_expediente['fal_nombre']} {datos_expediente['fal_apellido_p']} {datos_expediente['fal_apellido_m'] or ''}".strip()
            nombre_representante = f"{datos_expediente['rep_nombre'] or ''} {datos_expediente['rep_apellido_p'] or ''} {datos_expediente['rep_apellido_m'] or ''}".strip()
            nombre_funcionario_jefatura = f"{funcionario_jefatura['nombres'] or ''} {funcionario_jefatura['apellido_p'] or ''} {funcionario_jefatura['apellido_m'] or ''}".strip()
            
            # Generar número de resolución (usar folio o generar uno)
            numero_resolucion = datos_expediente['folio'] or f"RES-{expediente_id:03d}-{datetime.now().year}"
            
            # Contexto para el template
            context = {
                'NUMERO_CORRELATIVO': numero_resolucion,
                'FECHA_APROBACION': formatear_fecha(calculo['fecha_calculo']),
                'NOMBRE_CAUSANTE': nombre_causante,
                'RUT_CAUSANTE': formatear_rut(datos_expediente['fal_run']),
                'FECHA_FALLECIMIENTO': formatear_fecha(datos_expediente['fal_fecha_defuncion']),
                'NOMBRE_REPRESENTANTE': nombre_representante,
                'RUT_REPRESENTANTE': formatear_rut(datos_expediente['rep_rut']) if datos_expediente['rep_rut'] else '',
                'NOMBRE_FALLECIDA': nombre_causante,
                'VALOR_SALDO_INSOLUTO': formatear_moneda(calculo['total_calculado']),
                'FUNCIONARIO_JEFATURA': nombre_funcionario_jefatura,
                'FIRMA_FUNCIONARIO': nombre_funcionario_jefatura  # Funcionario de jefatura que inició sesión
            }
            
            # 5. Cargar template HTML y generar PDF directamente
            template_html_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'templates', 'resolucion_template.html')
            
            if not os.path.exists(template_html_path):
                cur.close()
                conn.close()
                return jsonify({'error': 'Template HTML de resolución no encontrado'}), 500
            
            # Leer el template HTML
            with open(template_html_path, 'r', encoding='utf-8') as f:
                html_template = f.read()
            
            # Renderizar el HTML con los datos usando Jinja2
            html_content = render_template_string(html_template, **context)
            
            # 6. Generar PDF directamente desde HTML usando xhtml2pdf
            if not XHTML2PDF_AVAILABLE:
                cur.close()
                conn.close()
                return jsonify({'error': 'xhtml2pdf no está disponible. Por favor, instale las dependencias correctas.'}), 500
            
            try:
                pdf_output = io.BytesIO()
                
                # Generar PDF desde HTML
                pisa_status = pisa.CreatePDF(
                    src=html_content,
                    dest=pdf_output,
                    encoding='utf-8'
                )
                
                if pisa_status.err:
                    raise Exception(f'Error generando PDF: {pisa_status.err}')
                
                pdf_output.seek(0)
                
                # Verificar que el PDF se generó correctamente
                pdf_data = pdf_output.read()
                if not pdf_data.startswith(b'%PDF'):
                    raise Exception('El archivo generado no es un PDF válido')
                
                pdf_output.seek(0)
                print('✅ PDF generado correctamente con xhtml2pdf')
                
                cur.close()
                conn.close()
                
                # Retornar el archivo PDF
                nombre_archivo = f"resolucion_{expediente_id}_{datetime.now().strftime('%Y%m%d')}.pdf"
                
                return send_file(
                    pdf_output,
                    mimetype='application/pdf',
                    as_attachment=True,
                    download_name=nombre_archivo
                )
                
            except Exception as pdf_error:
                print(f'❌ Error generando PDF con xhtml2pdf: {pdf_error}')
                import traceback
                traceback.print_exc()
                cur.close()
                conn.close()
                return jsonify({'error': f'Error generando PDF: {str(pdf_error)}'}), 500
            
        except Exception as e:
            print(f'❌ Error generando resolución: {e}')
            import traceback
            traceback.print_exc()
            if 'conn' in locals():
                conn.close()
            return jsonify({'error': f'Error interno del servidor: {str(e)}'}), 500

