#!/usr/bin/env python3
"""
Script de inicio para el servidor Flask
"""

import sys
import subprocess
import os

def check_python_version():
    """Verificar versión de Python"""
    if sys.version_info < (3, 8):
        print("❌ Se requiere Python 3.8 o superior")
        print(f"   Versión actual: {sys.version}")
        return False
    print(f"✅ Python {sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}")
    return True

def install_requirements():
    """Instalar dependencias si es necesario"""
    if not os.path.exists('requirements.txt'):
        print("❌ No se encontró requirements.txt")
        return False
    
    print("📦 Instalando dependencias...")
    try:
        subprocess.check_call([sys.executable, '-m', 'pip', 'install', '-r', 'requirements.txt'])
        print("✅ Dependencias instaladas correctamente")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Error instalando dependencias: {e}")
        return False

def main():
    """Función principal"""
    print("🚀 Iniciando servidor Flask - Sistema de Saldo Insoluto")
    print("=" * 60)
    
    # Verificar Python
    if not check_python_version():
        sys.exit(1)
    
    # Instalar dependencias
    if not install_requirements():
        sys.exit(1)
    
    # Iniciar servidor
    print("\n🌐 Iniciando servidor Flask...")
    try:
        from app import app
        app.run(host='0.0.0.0', port=3001, debug=True)
    except ImportError as e:
        print(f"❌ Error importando aplicación: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Error iniciando servidor: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main()

























