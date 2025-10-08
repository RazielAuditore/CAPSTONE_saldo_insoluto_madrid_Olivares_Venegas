# Backend Flask - Sistema de Saldo Insoluto

Este es el backend del sistema de saldo insoluto implementado en **Flask** (Python).

## Características

- ✅ **Flask** como framework web
- ✅ **PostgreSQL** como base de datos
- ✅ **psycopg2** para conexión a PostgreSQL
- ✅ **Flask-CORS** para permitir peticiones desde el frontend
- ✅ **Sistema de expedientes unificado**
- ✅ **APIs RESTful** para todas las operaciones
- ✅ **Manejo de transacciones** de base de datos
- ✅ **Firmas digitales** con HMAC-SHA256

## Instalación

1. **Instalar Python** (versión 3.8 o superior)

2. **Instalar dependencias:**
```bash
pip install -r requirements.txt
```

3. **Configurar base de datos:**
   - Asegúrate de que PostgreSQL esté corriendo
   - Verifica la configuración en `config.env`

4. **Ejecutar el servidor:**
```bash
python app.py
```

## Estructura del Proyecto

```
backend_flask/
├── app.py              # Aplicación principal Flask
├── config.py           # Configuración de la aplicación
├── config.env          # Variables de entorno
├── requirements.txt    # Dependencias de Python
└── README.md          # Este archivo
```

## APIs Disponibles

### POST /api/solicitudes
Crear una nueva solicitud de saldo insoluto

### POST /api/solicitudes/{id}/firma-representante
Firmar como representante

### POST /api/solicitudes/{id}/firma-funcionario
Firmar como funcionario

### GET /api/expediente/{id}
Obtener un expediente completo

### GET /api/health
Verificar estado del servidor

## Configuración

Edita el archivo `config.env` para configurar:
- Conexión a PostgreSQL
- Puerto del servidor
- Configuraciones de Flask

## Comparación con Node.js

| Característica | Node.js | Flask |
|----------------|---------|-------|
| Lenguaje | JavaScript | Python |
| Framework | Express.js | Flask |
| Base de datos | pg (node-postgres) | psycopg2 |
| Sintaxis | Más verbosa | Más limpia |
| Manejo de errores | Try/catch | Try/except |
| Transacciones | Manual | Manual |

## Ventajas de Flask

- ✅ **Sintaxis más limpia** y legible
- ✅ **Mejor manejo de errores** con Python
- ✅ **Más fácil de debuggear**
- ✅ **Excelente para APIs REST**
- ✅ **Gran ecosistema** de librerías
- ✅ **Mejor para desarrollo rápido**

## Uso

1. **Iniciar el servidor:**
```bash
python app.py
```

2. **El servidor estará disponible en:**
   - URL: http://localhost:3001
   - Health check: http://localhost:3001/api/health

3. **Usar el mismo frontend** (`formularioSaldoInsoluto.html`) que funciona con Node.js

