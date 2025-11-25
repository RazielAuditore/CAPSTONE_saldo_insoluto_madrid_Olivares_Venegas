"""
Servicio para cargar y buscar datos en archivos Excel
"""
import os
import pandas as pd
from utils.helpers import formatear_rut

# Cache de DataFrames
_df_representantes = None
_df_causantes = None
_df_beneficiarios = None
_excel_loaded = False

def normalizar_rut(rut):
    """Normalizar RUT removiendo puntos y guiones, y convirtiendo a mayúsculas"""
    if not rut:
        return ''
    return str(rut).replace('.', '').replace('-', '').upper().strip()

def cargar_excel():
    """Cargar los archivos Excel en memoria"""
    global _df_representantes, _df_causantes, _df_beneficiarios, _excel_loaded
    
    try:
        # Obtener ruta base del proyecto
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        datos_dir = os.path.join(base_dir, 'datos_prueba')
        
        # Rutas de los archivos Excel
        rep_path = os.path.join(datos_dir, 'representantes.xlsx')
        caus_path = os.path.join(datos_dir, 'causantes.xlsx')
        ben_path = os.path.join(datos_dir, 'beneficiarios.xlsx')
        
        # Verificar que los archivos existan
        if not os.path.exists(rep_path):
            print(f'⚠️ Archivo no encontrado: {rep_path}')
            return False
        if not os.path.exists(caus_path):
            print(f'⚠️ Archivo no encontrado: {caus_path}')
            return False
        if not os.path.exists(ben_path):
            print(f'⚠️ Archivo no encontrado: {ben_path}')
            return False
        
        # Cargar Excel
        _df_representantes = pd.read_excel(rep_path, engine='openpyxl')
        _df_causantes = pd.read_excel(caus_path, engine='openpyxl')
        _df_beneficiarios = pd.read_excel(ben_path, engine='openpyxl')
        
        # Mapear nombres de columnas reales a nombres esperados
        # Representantes: usar nombres reales del Excel
        col_rut_rep = 'RUT Representante' if 'RUT Representante' in _df_representantes.columns else 'rut'
        col_rut_caus = 'RUT Causante' if 'RUT Causante' in _df_causantes.columns else 'rut'
        
        # Normalizar RUTs en los DataFrames para búsquedas rápidas
        if col_rut_rep in _df_representantes.columns:
            _df_representantes['rut_normalizado'] = _df_representantes[col_rut_rep].apply(normalizar_rut)
            # Renombrar columna para facilitar acceso
            _df_representantes = _df_representantes.rename(columns={col_rut_rep: 'rut'})
        if col_rut_caus in _df_causantes.columns:
            _df_causantes['rut_normalizado'] = _df_causantes[col_rut_caus].apply(normalizar_rut)
            # Renombrar columna para facilitar acceso
            _df_causantes = _df_causantes.rename(columns={col_rut_caus: 'rut'})
        
        # Renombrar otras columnas de representantes
        rename_rep = {
            'Nombres': 'nombre',
            'Apellido Paterno': 'apellido_paterno',
            'Apellido Materno': 'apellido_materno',
            'Domicilio': 'direccion',
            'Comuna': 'comuna',
            'Región': 'region',
            'Teléfono': 'telefono',
            'Email': 'email'
        }
        for old, new in rename_rep.items():
            if old in _df_representantes.columns:
                _df_representantes = _df_representantes.rename(columns={old: new})
        
        # Renombrar otras columnas de causantes
        rename_caus = {
            'Nombres': 'nombre',
            'Apellido Paterno': 'apellido_paterno',
            'Apellido Materno': 'apellido_materno',
            'Comuna fallecimiento': 'comuna_defuncion',
            'Nacionalidad': 'nacionalidad',
            'Fecha Defunción': 'fecha_defuncion'
        }
        for old, new in rename_caus.items():
            if old in _df_causantes.columns:
                _df_causantes = _df_causantes.rename(columns={old: new})
        
        # Beneficiarios: buscar columna de RUT causante
        col_rut_caus_ben = None
        for col in _df_beneficiarios.columns:
            if 'causante' in col.lower() and 'rut' in col.lower():
                col_rut_caus_ben = col
                break
        
        if col_rut_caus_ben:
            _df_beneficiarios['rut_causante_normalizado'] = _df_beneficiarios[col_rut_caus_ben].apply(normalizar_rut)
            _df_beneficiarios = _df_beneficiarios.rename(columns={col_rut_caus_ben: 'rut_causante'})
        
        # Buscar y normalizar columna de RUT beneficiario
        col_rut_ben = None
        for col in _df_beneficiarios.columns:
            col_lower = col.lower()
            if ('beneficiario' in col_lower and 'rut' in col_lower) or col_lower in ['rut_beneficiario', 'run', 'rut beneficiario']:
                col_rut_ben = col
                break
        
        if col_rut_ben:
            _df_beneficiarios['rut_beneficiario_normalizado'] = _df_beneficiarios[col_rut_ben].apply(normalizar_rut)
            if col_rut_ben != 'rut_beneficiario':
                _df_beneficiarios = _df_beneficiarios.rename(columns={col_rut_ben: 'rut_beneficiario'})
        
        # Renombrar columnas comunes de beneficiarios si existen
        rename_ben = {
            'Nombre completo': 'nombre_completo',
            'Nombre': 'nombre_completo',
            'Parentesco': 'parentesco',
        }
        for old, new in rename_ben.items():
            if old in _df_beneficiarios.columns:
                _df_beneficiarios = _df_beneficiarios.rename(columns={old: new})
        
        _excel_loaded = True
        print(f'✅ Excel cargados exitosamente')
        print(f'   - Representantes: {len(_df_representantes)} registros')
        print(f'   - Causantes: {len(_df_causantes)} registros')
        print(f'   - Beneficiarios: {len(_df_beneficiarios)} registros')
        return True
        
    except Exception as e:
        print(f'❌ Error cargando Excel: {str(e)}')
        _excel_loaded = False
        return False

def recargar_excel():
    """Recargar los archivos Excel (útil después de actualizarlos)"""
    global _excel_loaded
    _excel_loaded = False
    return cargar_excel()

def buscar_representante(rut):
    """Buscar representante por RUT"""
    global _df_representantes, _excel_loaded
    
    if not _excel_loaded:
        if not cargar_excel():
            return None
    
    if _df_representantes is None or _df_representantes.empty:
        return None
    
    # Verificar que existe la columna rut_normalizado
    if 'rut_normalizado' not in _df_representantes.columns:
        return None
    
    rut_norm = normalizar_rut(rut)
    
    # Buscar por RUT normalizado
    resultado = _df_representantes[_df_representantes['rut_normalizado'] == rut_norm]
    
    if resultado.empty:
        return None
    
    # Obtener primera fila
    row = resultado.iloc[0]
    
    # Construir diccionario con los datos, formateando el RUT
    datos = {
        'rut': formatear_rut(str(row.get('rut', ''))),
        'calidad': str(row.get('calidad', '')).strip() if pd.notna(row.get('calidad')) else '',
        'nombre': str(row.get('nombre', '')).strip() if pd.notna(row.get('nombre')) else '',
        'apellido_paterno': str(row.get('apellido_paterno', '')).strip() if pd.notna(row.get('apellido_paterno')) else '',
        'apellido_materno': str(row.get('apellido_materno', '')).strip() if pd.notna(row.get('apellido_materno')) else '',
        'telefono': str(row.get('telefono', '')).strip() if pd.notna(row.get('telefono')) else '',
        'direccion': str(row.get('direccion', '')).strip() if pd.notna(row.get('direccion')) else '',
        'comuna': str(row.get('comuna', '')).strip() if pd.notna(row.get('comuna')) else '',
        'region': str(row.get('region', '')).strip() if pd.notna(row.get('region')) else '',
        'email': str(row.get('email', '')).strip() if pd.notna(row.get('email')) else ''
    }
    
    return datos

def buscar_causante(rut):
    """Buscar causante por RUT"""
    global _df_causantes, _excel_loaded
    
    if not _excel_loaded:
        if not cargar_excel():
            return None
    
    if _df_causantes is None or _df_causantes.empty:
        return None
    
    # Verificar que existe la columna rut_normalizado
    if 'rut_normalizado' not in _df_causantes.columns:
        return None
    
    rut_norm = normalizar_rut(rut)
    
    # Buscar por RUT normalizado
    resultado = _df_causantes[_df_causantes['rut_normalizado'] == rut_norm]
    
    if resultado.empty:
        return None
    
    # Obtener primera fila
    row = resultado.iloc[0]
    
    # Formatear fecha si existe
    fecha_def = row.get('fecha_defuncion', '')
    if pd.notna(fecha_def) and fecha_def != '':
        if isinstance(fecha_def, pd.Timestamp):
            fecha_def = fecha_def.strftime('%Y-%m-%d')
        else:
            fecha_def = str(fecha_def).split(' ')[0]  # Tomar solo la fecha si hay hora
    else:
        fecha_def = ''
    
    # Construir diccionario con los datos, formateando el RUT
    datos = {
        'rut': formatear_rut(str(row.get('rut', ''))),
        'nacionalidad': str(row.get('nacionalidad', '')).strip() if pd.notna(row.get('nacionalidad')) else '',
        'nombre': str(row.get('nombre', '')).strip() if pd.notna(row.get('nombre')) else '',
        'apellido_paterno': str(row.get('apellido_paterno', '')).strip() if pd.notna(row.get('apellido_paterno')) else '',
        'apellido_materno': str(row.get('apellido_materno', '')).strip() if pd.notna(row.get('apellido_materno')) else '',
        'fecha_defuncion': fecha_def,
        'comuna_defuncion': str(row.get('comuna_defuncion', '')).strip() if pd.notna(row.get('comuna_defuncion')) else ''
    }
    
    return datos

def buscar_beneficiarios(rut_causante):
    """Buscar beneficiarios por RUT del causante"""
    global _df_beneficiarios, _excel_loaded
    
    if not _excel_loaded:
        if not cargar_excel():
            return []
    
    if _df_beneficiarios is None or _df_beneficiarios.empty:
        return []
    
    # Verificar que existe la columna rut_causante_normalizado
    if 'rut_causante_normalizado' not in _df_beneficiarios.columns:
        return []
    
    rut_norm = normalizar_rut(rut_causante)
    
    # Buscar por RUT causante normalizado
    resultado = _df_beneficiarios[_df_beneficiarios['rut_causante_normalizado'] == rut_norm]
    
    if resultado.empty:
        return []
    
    # Convertir a lista de diccionarios
    beneficiarios = []
    for _, row in resultado.iterrows():
        ben = {
            'rut_beneficiario': formatear_rut(str(row.get('rut_beneficiario', ''))) if pd.notna(row.get('rut_beneficiario')) else '',
            'nombre_completo': str(row.get('nombre_completo', '')).strip() if pd.notna(row.get('nombre_completo')) else '',
            'parentesco': str(row.get('parentesco', '')).strip() if pd.notna(row.get('parentesco')) else '',
        }
        beneficiarios.append(ben)
    
    return beneficiarios

def buscar_beneficiario_por_rut(rut_beneficiario):
    """Buscar un beneficiario individual por su RUT y retornar solo el nombre"""
    global _df_beneficiarios, _excel_loaded
    
    if not _excel_loaded:
        if not cargar_excel():
            return None
    
    if _df_beneficiarios is None or _df_beneficiarios.empty:
        return None
    
    # Verificar que existe la columna rut_beneficiario_normalizado
    if 'rut_beneficiario_normalizado' not in _df_beneficiarios.columns:
        return None
    
    rut_norm = normalizar_rut(rut_beneficiario)
    
    # Buscar por RUT normalizado
    resultado = _df_beneficiarios[_df_beneficiarios['rut_beneficiario_normalizado'] == rut_norm]
    
    if resultado.empty:
        return None
    
    # Obtener primera fila
    row = resultado.iloc[0]
    
    # Retornar solo el nombre completo
    nombre = row.get('nombre_completo', '')
    if pd.notna(nombre) and nombre != '':
        return {'nombre': str(nombre).strip()}
    
    return None

def esta_cargado():
    """Verificar si los Excel están cargados"""
    return _excel_loaded

