"""
Servicio para cargar y buscar datos en archivos Excel
Implementado como clase singleton para mejor encapsulación y gestión de estado
"""
import os
import pandas as pd
from utils.helpers import formatear_rut


class ExcelService:
    """
    Servicio singleton para gestionar la carga y búsqueda de datos en archivos Excel.
    Mantiene los DataFrames en memoria para búsquedas rápidas.
    """
    _instance = None
    _initialized = False
    
    def __new__(cls):
        """Implementar patrón singleton"""
        if cls._instance is None:
            cls._instance = super(ExcelService, cls).__new__(cls)
        return cls._instance
    
    def __init__(self):
        """Inicializar el servicio (solo una vez)"""
        if not self._initialized:
            self._df_representantes = None
            self._df_causantes = None
            self._df_beneficiarios = None
            self._excel_loaded = False
            self._base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            self._datos_dir = os.path.join(self._base_dir, 'datos_prueba')
            ExcelService._initialized = True
    
    @staticmethod
    def normalizar_rut(rut):
        """Normalizar RUT removiendo puntos y guiones, y convirtiendo a mayúsculas"""
        if not rut:
            return ''
        return str(rut).replace('.', '').replace('-', '').upper().strip()
    
    def cargar_excel(self):
        """Cargar los archivos Excel en memoria"""
        try:
            # Rutas de los archivos Excel
            rep_path = os.path.join(self._datos_dir, 'representantes.xlsx')
            caus_path = os.path.join(self._datos_dir, 'causantes.xlsx')
            ben_path = os.path.join(self._datos_dir, 'beneficiarios.xlsx')
            
            # Verificar que los archivos existan
            archivos_faltantes = []
            if not os.path.exists(rep_path):
                archivos_faltantes.append(rep_path)
            if not os.path.exists(caus_path):
                archivos_faltantes.append(caus_path)
            if not os.path.exists(ben_path):
                archivos_faltantes.append(ben_path)
            
            if archivos_faltantes:
                for archivo in archivos_faltantes:
                    print(f'⚠️ Archivo no encontrado: {archivo}')
                return False
            
            # Cargar Excel
            self._df_representantes = pd.read_excel(rep_path, engine='openpyxl')
            self._df_causantes = pd.read_excel(caus_path, engine='openpyxl')
            self._df_beneficiarios = pd.read_excel(ben_path, engine='openpyxl')
            
            # Procesar representantes
            self._procesar_representantes()
            
            # Procesar causantes
            self._procesar_causantes()
            
            # Procesar beneficiarios
            self._procesar_beneficiarios()
            
            self._excel_loaded = True
            print(f'✅ Excel cargados exitosamente')
            print(f'   - Representantes: {len(self._df_representantes)} registros')
            print(f'   - Causantes: {len(self._df_causantes)} registros')
            print(f'   - Beneficiarios: {len(self._df_beneficiarios)} registros')
            return True
            
        except Exception as e:
            print(f'❌ Error cargando Excel: {str(e)}')
            self._excel_loaded = False
            return False
    
    def _procesar_representantes(self):
        """Procesar y normalizar datos de representantes"""
        col_rut_rep = 'RUT Representante' if 'RUT Representante' in self._df_representantes.columns else 'rut'
        
        if col_rut_rep in self._df_representantes.columns:
            self._df_representantes['rut_normalizado'] = self._df_representantes[col_rut_rep].apply(self.normalizar_rut)
            self._df_representantes = self._df_representantes.rename(columns={col_rut_rep: 'rut'})
        
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
            if old in self._df_representantes.columns:
                self._df_representantes = self._df_representantes.rename(columns={old: new})
    
    def _procesar_causantes(self):
        """Procesar y normalizar datos de causantes"""
        col_rut_caus = 'RUT Causante' if 'RUT Causante' in self._df_causantes.columns else 'rut'
        
        if col_rut_caus in self._df_causantes.columns:
            self._df_causantes['rut_normalizado'] = self._df_causantes[col_rut_caus].apply(self.normalizar_rut)
            self._df_causantes = self._df_causantes.rename(columns={col_rut_caus: 'rut'})
        
        rename_caus = {
            'Nombres': 'nombre',
            'Apellido Paterno': 'apellido_paterno',
            'Apellido Materno': 'apellido_materno',
            'Comuna fallecimiento': 'comuna_defuncion',
            'Nacionalidad': 'nacionalidad',
            'Fecha Defunción': 'fecha_defuncion'
        }
        for old, new in rename_caus.items():
            if old in self._df_causantes.columns:
                self._df_causantes = self._df_causantes.rename(columns={old: new})
    
    def _procesar_beneficiarios(self):
        """Procesar y normalizar datos de beneficiarios"""
        # Buscar columna de RUT causante
        col_rut_caus_ben = None
        for col in self._df_beneficiarios.columns:
            if 'causante' in col.lower() and 'rut' in col.lower():
                col_rut_caus_ben = col
                break
        
        if col_rut_caus_ben:
            self._df_beneficiarios['rut_causante_normalizado'] = self._df_beneficiarios[col_rut_caus_ben].apply(self.normalizar_rut)
            self._df_beneficiarios = self._df_beneficiarios.rename(columns={col_rut_caus_ben: 'rut_causante'})
        
        # Buscar y normalizar columna de RUT beneficiario
        col_rut_ben = None
        for col in self._df_beneficiarios.columns:
            col_lower = col.lower()
            if ('beneficiario' in col_lower and 'rut' in col_lower) or col_lower in ['rut_beneficiario', 'run', 'rut beneficiario']:
                col_rut_ben = col
                break
        
        if col_rut_ben:
            self._df_beneficiarios['rut_beneficiario_normalizado'] = self._df_beneficiarios[col_rut_ben].apply(self.normalizar_rut)
            if col_rut_ben != 'rut_beneficiario':
                self._df_beneficiarios = self._df_beneficiarios.rename(columns={col_rut_ben: 'rut_beneficiario'})
        
        rename_ben = {
            'Nombre completo': 'nombre_completo',
            'Nombre': 'nombre_completo',
            'Parentesco': 'parentesco',
        }
        for old, new in rename_ben.items():
            if old in self._df_beneficiarios.columns:
                self._df_beneficiarios = self._df_beneficiarios.rename(columns={old: new})
    
    def recargar_excel(self):
        """Recargar los archivos Excel (útil después de actualizarlos)"""
        self._excel_loaded = False
        return self.cargar_excel()
    
    def buscar_representante(self, rut):
        """Buscar representante por RUT"""
        if not self._excel_loaded:
            if not self.cargar_excel():
                return None
        
        if self._df_representantes is None or self._df_representantes.empty:
            return None
        
        if 'rut_normalizado' not in self._df_representantes.columns:
            return None
        
        rut_norm = self.normalizar_rut(rut)
        resultado = self._df_representantes[self._df_representantes['rut_normalizado'] == rut_norm]
        
        if resultado.empty:
            return None
        
        row = resultado.iloc[0]
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
    
    def buscar_causante(self, rut):
        """Buscar causante por RUT"""
        if not self._excel_loaded:
            if not self.cargar_excel():
                return None
        
        if self._df_causantes is None or self._df_causantes.empty:
            return None
        
        if 'rut_normalizado' not in self._df_causantes.columns:
            return None
        
        rut_norm = self.normalizar_rut(rut)
        resultado = self._df_causantes[self._df_causantes['rut_normalizado'] == rut_norm]
        
        if resultado.empty:
            return None
        
        row = resultado.iloc[0]
        
        # Formatear fecha si existe
        fecha_def = row.get('fecha_defuncion', '')
        if pd.notna(fecha_def) and fecha_def != '':
            if isinstance(fecha_def, pd.Timestamp):
                fecha_def = fecha_def.strftime('%Y-%m-%d')
            else:
                fecha_def = str(fecha_def).split(' ')[0]
        else:
            fecha_def = ''
        
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
    
    def buscar_beneficiarios(self, rut_causante):
        """Buscar beneficiarios por RUT del causante"""
        if not self._excel_loaded:
            if not self.cargar_excel():
                return []
        
        if self._df_beneficiarios is None or self._df_beneficiarios.empty:
            return []
        
        if 'rut_causante_normalizado' not in self._df_beneficiarios.columns:
            return []
        
        rut_norm = self.normalizar_rut(rut_causante)
        resultado = self._df_beneficiarios[self._df_beneficiarios['rut_causante_normalizado'] == rut_norm]
        
        if resultado.empty:
            return []
        
        beneficiarios = []
        for _, row in resultado.iterrows():
            ben = {
                'rut_beneficiario': formatear_rut(str(row.get('rut_beneficiario', ''))) if pd.notna(row.get('rut_beneficiario')) else '',
                'nombre_completo': str(row.get('nombre_completo', '')).strip() if pd.notna(row.get('nombre_completo')) else '',
                'parentesco': str(row.get('parentesco', '')).strip() if pd.notna(row.get('parentesco')) else '',
            }
            beneficiarios.append(ben)
        
        return beneficiarios
    
    def buscar_beneficiario_por_rut(self, rut_beneficiario):
        """Buscar un beneficiario individual por su RUT y retornar solo el nombre"""
        if not self._excel_loaded:
            if not self.cargar_excel():
                return None
        
        if self._df_beneficiarios is None or self._df_beneficiarios.empty:
            return None
        
        if 'rut_beneficiario_normalizado' not in self._df_beneficiarios.columns:
            return None
        
        rut_norm = self.normalizar_rut(rut_beneficiario)
        resultado = self._df_beneficiarios[self._df_beneficiarios['rut_beneficiario_normalizado'] == rut_norm]
        
        if resultado.empty:
            return None
        
        row = resultado.iloc[0]
        nombre = row.get('nombre_completo', '')
        if pd.notna(nombre) and nombre != '':
            return {'nombre': str(nombre).strip()}
        
        return None
    
    def esta_cargado(self):
        """Verificar si los Excel están cargados"""
        return self._excel_loaded


# Instancia singleton global para mantener compatibilidad con código existente
_excel_service = ExcelService()

# Funciones de compatibilidad para mantener la API existente
def normalizar_rut(rut):
    """Normalizar RUT - función de compatibilidad"""
    return ExcelService.normalizar_rut(rut)

def cargar_excel():
    """Cargar Excel - función de compatibilidad"""
    return _excel_service.cargar_excel()

def recargar_excel():
    """Recargar Excel - función de compatibilidad"""
    return _excel_service.recargar_excel()

def buscar_representante(rut):
    """Buscar representante - función de compatibilidad"""
    return _excel_service.buscar_representante(rut)

def buscar_causante(rut):
    """Buscar causante - función de compatibilidad"""
    return _excel_service.buscar_causante(rut)

def buscar_beneficiarios(rut_causante):
    """Buscar beneficiarios - función de compatibilidad"""
    return _excel_service.buscar_beneficiarios(rut_causante)

def buscar_beneficiario_por_rut(rut_beneficiario):
    """Buscar beneficiario por RUT - función de compatibilidad"""
    return _excel_service.buscar_beneficiario_por_rut(rut_beneficiario)

def esta_cargado():
    """Verificar si está cargado - función de compatibilidad"""
    return _excel_service.esta_cargado()
