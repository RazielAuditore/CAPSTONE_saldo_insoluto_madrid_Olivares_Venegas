"""
Parche para compatibilidad entre Flask-Session y Werkzeug 3.x
Este módulo aplica un parche necesario para que Flask-Session funcione correctamente
con versiones recientes de Werkzeug que esperan strings en lugar de bytes para cookies.
"""
from werkzeug.sansio.response import Response

# Guardar la función original
_original_set_cookie = Response.set_cookie

def _patched_set_cookie(self, *args, **kwargs):
    """
    Parche para convertir value de bytes a string si es necesario.
    Esto es necesario para compatibilidad con Flask-Session y Werkzeug 3.x
    """
    # Convertir value de bytes a string si es necesario
    if len(args) > 1 and isinstance(args[1], bytes):
        args = (args[0], args[1].decode('utf-8'), *args[2:])
    elif 'value' in kwargs and isinstance(kwargs['value'], bytes):
        kwargs['value'] = kwargs['value'].decode('utf-8')
    
    # Llamar a la función original con todos los argumentos
    return _original_set_cookie(self, *args, **kwargs)

def apply_patch():
    """Aplicar el parche de compatibilidad"""
    Response.set_cookie = _patched_set_cookie

def remove_patch():
    """Remover el parche (útil para testing)"""
    Response.set_cookie = _original_set_cookie

