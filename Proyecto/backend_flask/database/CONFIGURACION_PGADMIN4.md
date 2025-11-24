# Configuración de PostgreSQL con pgAdmin4

Esta guía te ayudará a configurar la base de datos PostgreSQL para el proyecto de Saldo Insoluto usando pgAdmin4.

## 📋 Requisitos Previos

1. **PostgreSQL instalado** (versión 11 o superior)
2. **pgAdmin4 instalado** (versión 4 o superior)
3. Python 3.8+ con las dependencias del proyecto instaladas

## 🔧 Paso 1: Configurar PostgreSQL

### 1.1. Verificar que PostgreSQL esté corriendo

En Windows:
```powershell
# Verificar el servicio
Get-Service postgresql*

# Si no está corriendo, iniciarlo
Start-Service postgresql-x64-XX
```

En Linux/Mac:
```bash
# Verificar estado
sudo systemctl status postgresql

# Iniciar si es necesario
sudo systemctl start postgresql
```

### 1.2. Conectar a PostgreSQL

Abre pgAdmin4 y conéctate a tu servidor PostgreSQL. Si es la primera vez:
- **Host**: `localhost` o `127.0.0.1`
- **Port**: `5432` (puerto por defecto, o el puerto que configuraste)
- **Username**: `postgres`
- **Password**: La contraseña que configuraste durante la instalación

## 🗄️ Paso 2: Crear la Base de Datos

### Opción A: Desde pgAdmin4 (Interfaz Gráfica)

1. **Clic derecho** en "Databases" → **Create** → **Database...**
2. Configura la base de datos:
   - **Database name**: `saldo_insoluto` (o el nombre que prefieras)
   - **Owner**: `postgres`
   - **Encoding**: `UTF8`
   - **Template**: `template0`
3. Click en **Save**

### Opción B: Desde la Query Tool de pgAdmin4

1. Click derecho en tu servidor → **Query Tool**
2. Ejecuta:
```sql
CREATE DATABASE saldo_insoluto
    WITH OWNER = postgres
    ENCODING = 'UTF8'
    LC_COLLATE = 'es_CL.UTF-8'
    LC_CTYPE = 'es_CL.UTF-8'
    TEMPLATE = template0;
```

## 📝 Paso 3: Ejecutar el Script de Inicialización

### 3.1. Cargar el script en pgAdmin4

1. En pgAdmin4, expande tu servidor → **Databases** → `saldo_insoluto`
2. Click derecho en `saldo_insoluto` → **Query Tool**
3. Click en el icono de **Open File** (📁) o presiona `Ctrl+O`
4. Navega a: `Proyecto/backend_flask/database/init_database.sql`
5. Click en **Open**

### 3.2. Ejecutar el script

1. Verifica que el script esté cargado correctamente
2. Click en el botón **Execute/Refresh** (▶️) o presiona `F5`
3. Espera a que termine la ejecución
4. Deberías ver mensajes de confirmación:
   - ✅ Base de datos inicializada correctamente
   - ✅ Esquema app creado
   - ✅ Todas las tablas creadas
   - ✅ Triggers configurados
   - ✅ Usuario administrador creado

### 3.3. Verificar la creación

Ejecuta esta consulta para verificar que todas las tablas fueron creadas:

```sql
SELECT 
    table_schema,
    table_name
FROM information_schema.tables
WHERE table_schema = 'app'
ORDER BY table_name;
```

Deberías ver estas tablas:
- beneficiarios
- causante
- documentos_saldo_insoluto
- expediente
- firmas_beneficiarios
- funcionarios
- representante
- solicitudes
- usuarios_firma
- validacion

## ⚙️ Paso 4: Configurar la Conexión en el Proyecto

### 4.1. Actualizar config.env

Edita el archivo `Proyecto/backend_flask/config.env`:

```env
# Configuración de PostgreSQL
DB_HOST=127.0.0.1
DB_PORT=5432          # Puerto por defecto de PostgreSQL
DB_NAME=saldo_insoluto  # Nombre de la base de datos que creaste
DB_USER=postgres
DB_PASSWORD=tu_password_postgres  # Tu contraseña de PostgreSQL

# Configuración del servidor Flask
PORT=3001
HOST=0.0.0.0
DEBUG=True

# Configuración de Flask
SECRET_KEY=tu-clave-secreta-flask-super-segura-2024
```

**⚠️ IMPORTANTE**: 
- Reemplaza `tu_password_postgres` con tu contraseña real
- Verifica que `DB_PORT` coincida con el puerto de tu PostgreSQL
- El `DB_NAME` debe coincidir con el nombre de la base de datos que creaste

### 4.2. Probar la conexión

Desde la terminal, ejecuta:

```bash
cd Proyecto/backend_flask
python app.py
```

Deberías ver mensajes como:
```
✅ Conectado a PostgreSQL
📅 Hora del servidor: 2024-XX-XX XX:XX:XX
✅ Tabla firmas_beneficiarios creada exitosamente
✅ Servidor Flask ejecutándose en puerto 3001
🔗 URL: http://localhost:3001
```

## 🔐 Paso 5: Credenciales de Acceso

### Usuario Administrador por Defecto

El script crea un usuario administrador por defecto:

- **RUT**: `12345678-9`
- **Password**: `admin123`
- **Email**: `admin@sistema.cl`
- **Rol**: `administrador`

**⚠️ IMPORTANTE**: Cambia esta contraseña en producción.

## 🛠️ Paso 6: Comandos Útiles en pgAdmin4

### Ver todas las tablas del esquema app

```sql
SELECT * FROM app.funcionarios;
```

### Ver estructura de una tabla

1. En pgAdmin4, expande: `Databases` → `saldo_insoluto` → `Schemas` → `app` → `Tables`
2. Click derecho en cualquier tabla → **Properties**
3. Ve a la pestaña **Columns** para ver la estructura

### Ejecutar consultas personalizadas

```sql
-- Ver todos los expedientes
SELECT * FROM app.expediente ORDER BY fecha_creacion DESC;

-- Ver todos los funcionarios
SELECT id, rut, nombres, apellido_p, rol, activo FROM app.funcionarios;

-- Contar registros por tabla
SELECT 
    'expediente' as tabla, COUNT(*) as registros FROM app.expediente
UNION ALL
SELECT 'solicitudes', COUNT(*) FROM app.solicitudes
UNION ALL
SELECT 'funcionarios', COUNT(*) FROM app.funcionarios;
```

## 🔍 Solución de Problemas

### Error: "connection refused"

**Problema**: No se puede conectar a PostgreSQL

**Solución**:
1. Verifica que PostgreSQL esté corriendo
2. Revisa que el puerto en `config.env` sea correcto
3. Verifica las credenciales (usuario y contraseña)

### Error: "database does not exist"

**Problema**: La base de datos no existe

**Solución**:
1. Crea la base de datos siguiendo el Paso 2
2. Verifica el nombre en `config.env` (`DB_NAME`)

### Error: "schema app does not exist"

**Problema**: El esquema no fue creado

**Solución**:
1. Ejecuta nuevamente el script `init_database.sql`
2. Verifica que se ejecutó completamente sin errores

### Error: "permission denied"

**Problema**: El usuario no tiene permisos

**Solución**:
1. En pgAdmin4, ejecuta:
```sql
GRANT ALL PRIVILEGES ON SCHEMA app TO postgres;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA app TO postgres;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA app TO postgres;
```

## 📚 Recursos Adicionales

- [Documentación de PostgreSQL](https://www.postgresql.org/docs/)
- [Documentación de pgAdmin4](https://www.pgadmin.org/docs/)
- [Documentación de psycopg2](https://www.psycopg.org/docs/)

## ✅ Checklist de Configuración

- [ ] PostgreSQL instalado y corriendo
- [ ] pgAdmin4 instalado y conectado
- [ ] Base de datos `saldo_insoluto` creada
- [ ] Script `init_database.sql` ejecutado exitosamente
- [ ] Archivo `config.env` configurado correctamente
- [ ] Conexión probada con `python app.py`
- [ ] Todas las tablas visibles en pgAdmin4
- [ ] Usuario administrador funciona correctamente

## 🎉 ¡Listo!

Tu base de datos está configurada y lista para usar. Puedes empezar a trabajar con el proyecto.

Para más información sobre el proyecto, consulta el archivo `README.md`.


