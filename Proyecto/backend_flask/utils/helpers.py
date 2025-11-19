"""
Funciones auxiliares y de ayuda
"""
import hashlib
import bcrypt
from werkzeug.utils import secure_filename

# Configuración para archivos
ALLOWED_EXTENSIONS = {'pdf', 'png', 'jpg', 'jpeg', 'gif', 'doc', 'docx', 'xls', 'xlsx'}
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB máximo

def allowed_file(filename):
    """Verificar si el archivo tiene una extensión permitida"""
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def get_file_hash(file_data):
    """Generar hash SHA256 del archivo"""
    return hashlib.sha256(file_data).hexdigest()

def get_mime_type(filename):
    """Obtener tipo MIME basado en la extensión del archivo"""
    mime_types = {
        'pdf': 'application/pdf',
        'png': 'image/png',
        'jpg': 'image/jpeg',
        'jpeg': 'image/jpeg',
        'gif': 'image/gif',
        'doc': 'application/msword',
        'docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        'xls': 'application/vnd.ms-excel',
        'xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    }
    ext = filename.rsplit('.', 1)[1].lower()
    return mime_types.get(ext, 'application/octet-stream')

def validar_rut_chileno(rut):
    """Validar RUT chileno con algoritmo de dígito verificador"""
    try:
        print(f"🔍 Validando RUT: '{rut}'")
        
        # Limpiar RUT
        rut_limpio = rut.replace('.', '').replace('-', '').upper()
        print(f"🔍 RUT limpio: '{rut_limpio}'")
        
        if len(rut_limpio) < 8 or len(rut_limpio) > 9:
            print(f"❌ RUT muy corto/largo: {len(rut_limpio)} caracteres")
            return False
        
        # Separar número y dígito verificador
        numero = rut_limpio[:-1]
        dv = rut_limpio[-1]
        print(f"🔍 Número: '{numero}', DV: '{dv}'")
        
        # Validar que el número sea solo dígitos
        if not numero.isdigit():
            return False
        
        # Calcular dígito verificador
        suma = 0
        multiplicador = 2
        
        for digito in reversed(numero):
            suma += int(digito) * multiplicador
            multiplicador = multiplicador + 1 if multiplicador < 7 else 2
        
        resto = suma % 11
        dv_calculado = 11 - resto
        
        if dv_calculado == 11:
            dv_calculado = '0'
        elif dv_calculado == 10:
            dv_calculado = 'K'
        else:
            dv_calculado = str(dv_calculado)
        
        print(f"🔍 DV ingresado: '{dv}', DV calculado: '{dv_calculado}'")
        resultado = dv == dv_calculado
        print(f"🔍 Resultado validación: {resultado}")
        
        return resultado
        
    except Exception:
        return False

def hash_password(password):
    """Encriptar contraseña con bcrypt"""
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')

def formatear_rut(rut):
    """Formatear RUT chileno con puntos y guión (ej: 12.345.678-9)"""
    if not rut:
        return ''
    
    # Limpiar RUT
    rut_limpio = rut.replace('.', '').replace('-', '').upper()
    
    if len(rut_limpio) < 8:
        return rut  # Retornar original si es muy corto
    
    # Separar número y dígito verificador
    numero = rut_limpio[:-1]
    dv = rut_limpio[-1]
    
    # Formatear número con puntos
    numero_formateado = ''
    for i, digito in enumerate(reversed(numero)):
        if i > 0 and i % 3 == 0:
            numero_formateado = '.' + numero_formateado
        numero_formateado = digito + numero_formateado
    
    return f"{numero_formateado}-{dv}"

def formatear_fecha(fecha):
    """Formatear fecha a formato legible en español (ej: 15 de marzo de 2024)"""
    if not fecha:
        return ''
    
    from datetime import datetime
    
    # Si es string, convertir a datetime
    if isinstance(fecha, str):
        try:
            # Intentar diferentes formatos
            for fmt in ['%Y-%m-%d', '%Y-%m-%d %H:%M:%S', '%Y-%m-%dT%H:%M:%S']:
                try:
                    fecha = datetime.strptime(fecha.split('T')[0], fmt)
                    break
                except:
                    continue
        except:
            return str(fecha)
    
    # Meses en español
    meses = [
        'enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio',
        'julio', 'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre'
    ]
    
    dia = fecha.day
    mes = meses[fecha.month - 1]
    año = fecha.year
    
    return f"{dia} de {mes} de {año}"

def formatear_moneda(monto):
    """Formatear monto como moneda chilena (ej: $1.234.567)"""
    if monto is None:
        return '$0'
    
    # Convertir a float si es necesario
    try:
        monto_float = float(monto)
    except:
        return str(monto)
    
    # Formatear con separador de miles
    monto_str = f"{int(monto_float):,}".replace(',', '.')
    
    return f"${monto_str}"


