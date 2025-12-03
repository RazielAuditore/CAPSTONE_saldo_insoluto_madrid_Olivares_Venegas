import os
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv('config.env')

class Config:
    """Configuración de la aplicación Flask"""
    
    # Configuración de la base de datos
    DB_HOST = os.getenv('DB_HOST', '127.0.0.1')
    DB_PORT = os.getenv('DB_PORT', '5432')
    DB_NAME = os.getenv('DB_NAME', 'postgres')
    DB_USER = os.getenv('DB_USER', 'postgres')
    DB_PASSWORD = os.getenv('DB_PASSWORD', '1234')
    
    # Configuración del servidor
    PORT = int(os.getenv('PORT', '3001'))
    HOST = os.getenv('HOST', '0.0.0.0')
    DEBUG = os.getenv('DEBUG', 'True').lower() == 'true'
    
    # Configuración de Flask
    SECRET_KEY = os.getenv('SECRET_KEY', 'tu-clave-secreta-aqui')
    
    @property
    def DATABASE_CONFIG(self):
        """Configuración de la base de datos como diccionario"""
        return {
            'host': self.DB_HOST,
            'port': self.DB_PORT,
            'database': self.DB_NAME,
            'user': self.DB_USER,
            'password': self.DB_PASSWORD
        }

