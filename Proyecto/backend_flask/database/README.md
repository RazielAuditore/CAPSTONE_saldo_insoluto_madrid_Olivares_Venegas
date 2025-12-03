# Base de Datos - Sistema de Saldo Insoluto

Este directorio contiene los scripts y documentación para configurar la base de datos PostgreSQL del proyecto.

## 📁 Archivos

- **`init_database.sql`**: Script SQL completo para inicializar todas las tablas, esquemas y datos iniciales
- **`CONFIGURACION_PGADMIN4.md`**: Guía paso a paso para configurar la conexión usando pgAdmin4
- **`test_connection.py`**: Script de Python para probar la conexión a PostgreSQL
- **`README.md`**: Este archivo

## 🚀 Inicio Rápido

### 1. Crear la base de datos en pgAdmin4

1. Abre pgAdmin4
2. Conéctate a tu servidor PostgreSQL
3. Crea una nueva base de datos llamada `saldo_insoluto`

### 2. Ejecutar el script de inicialización

1. En pgAdmin4, abre la Query Tool
2. Abre el archivo `init_database.sql`
3. Ejecuta el script (F5)

### 3. Configurar la conexión

1. Edita `config.env` en el directorio raíz de `backend_flask`
2. Actualiza `DB_NAME` a `saldo_insoluto` si creaste una base de datos específica
3. Verifica que `DB_PASSWORD` coincida con tu contraseña de PostgreSQL

### 4. Probar la conexión

```bash
cd backend_flask
python database/test_connection.py
```

## 📚 Documentación Detallada

Para instrucciones detalladas, consulta:
- **[CONFIGURACION_PGADMIN4.md](CONFIGURACION_PGADMIN4.md)**: Guía completa de configuración

## 🗄️ Estructura de la Base de Datos

El esquema `app` contiene las siguientes tablas:

- **`expediente`**: Expedientes principales del sistema
- **`solicitudes`**: Solicitudes de saldo insoluto
- **`causante`**: Información del fallecido
- **`representante`**: Información del representante legal
- **`beneficiarios`**: Beneficiarios de las solicitudes
- **`funcionarios`**: Usuarios del sistema
- **`documentos_saldo_insoluto`**: Documentos asociados
- **`validacion`**: Estados de validación y firmas
- **`firmas_beneficiarios`**: Firmas de beneficiarios
- **`usuarios_firma`**: Usuarios para firma digital externa

## 🔐 Credenciales por Defecto

### Usuario Administrador

- **RUT**: `12345678-9`
- **Password**: `admin123`
- **Email**: `admin@sistema.cl`
- **Rol**: `administrador`

⚠️ **IMPORTANTE**: Cambia estas credenciales en producción.

## 🛠️ Herramientas

### Test de Conexión

```bash
python database/test_connection.py
```

Este script verifica:
- ✅ Conexión a PostgreSQL
- ✅ Existencia del esquema `app`
- ✅ Tablas creadas
- ✅ Usuario administrador

### Backup de la Base de Datos

```bash
# Desde pgAdmin4: Click derecho en la base de datos → Backup
# O desde terminal:
pg_dump -U postgres -d saldo_insoluto > backup_$(date +%Y%m%d).sql
```

### Restaurar Base de Datos

```bash
# Desde pgAdmin4: Click derecho en la base de datos → Restore
# O desde terminal:
psql -U postgres -d saldo_insoluto < backup_YYYYMMDD.sql
```

## 📝 Notas Importantes

1. **Puerto de PostgreSQL**: Por defecto, PostgreSQL usa el puerto `5432`. Si usas otro puerto, actualiza `DB_PORT` en `config.env`

2. **Esquema**: Todas las tablas están en el esquema `app`, por lo que las consultas deben usar `app.nombre_tabla`

3. **Triggers**: El script crea triggers automáticos para actualizar campos `updated_at` y `actualizado_en`

4. **Índices**: Se crean índices optimizados para mejorar el rendimiento de las consultas

## 🐛 Solución de Problemas

### Error: "connection refused"

- Verifica que PostgreSQL esté corriendo
- Revisa el puerto en `config.env`

### Error: "database does not exist"

- Crea la base de datos en pgAdmin4
- Actualiza `DB_NAME` en `config.env`

### Error: "schema app does not exist"

- Ejecuta `init_database.sql` nuevamente
- Verifica que el script se ejecutó sin errores

## 📞 Soporte

Para más información, consulta:
- [Documentación de PostgreSQL](https://www.postgresql.org/docs/)
- [Documentación de pgAdmin4](https://www.pgadmin.org/docs/)
- [README principal del proyecto](../README.md)


