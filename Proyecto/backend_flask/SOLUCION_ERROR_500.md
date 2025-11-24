# Solución de Error 500 en pgAdmin4

Este documento te ayudará a diagnosticar y resolver el error 500 que estás experimentando con pgAdmin4.

## 🔍 Diagnóstico del Error 500

El error 500 en pgAdmin4 puede tener varias causas. Vamos a diagnosticarlo paso a paso:

### Paso 1: Verificar que PostgreSQL esté corriendo

**En Windows (PowerShell):**
```powershell
Get-Service postgresql*
```

Si no está corriendo, inícialo:
```powershell
Start-Service postgresql-x64-XX  # Reemplaza XX con tu versión
```

**O desde los Servicios de Windows:**
1. Presiona `Win + R`, escribe `services.msc` y presiona Enter
2. Busca "postgresql" en la lista
3. Verifica que esté "En ejecución"
4. Si no está corriendo, click derecho → Iniciar

### Paso 2: Verificar el puerto de PostgreSQL

El archivo `config.env` usa el puerto **5432**. Verifica cuál es el puerto real de tu PostgreSQL:

**En Windows (PowerShell como Administrador):**
```powershell
netstat -ano | findstr :5432
netstat -ano | findstr :5433
```

**O revisa en pgAdmin4:**
1. Click derecho en tu servidor PostgreSQL → **Properties**
2. Ve a la pestaña **Connection**
3. Verifica el **Port**

### Paso 3: Verificar las credenciales en config.env

Edita `Proyecto/backend_flask/config.env` y verifica:
```env
DB_HOST=127.0.0.1
DB_PORT=5432          # Verifica que este sea el puerto correcto
DB_NAME=postgres      # Nombre de la base de datos
DB_USER=postgres      # Usuario de PostgreSQL
DB_PASSWORD=1234      # Tu contraseña real de PostgreSQL
```

**⚠️ IMPORTANTE:** Asegúrate de que `DB_PASSWORD` sea la contraseña real que configuraste durante la instalación de PostgreSQL.

### Paso 4: Probar la conexión manualmente

**Desde pgAdmin4:**
1. Abre pgAdmin4
2. En el panel izquierdo, expande **Servers**
3. Click derecho en tu servidor → **Query Tool**
4. Ejecuta esta consulta simple:
```sql
SELECT version();
```

Si esto funciona, PostgreSQL está bien configurado.

### Paso 5: Verificar que la base de datos exista

Ejecuta en pgAdmin4 (Query Tool):
```sql
SELECT datname FROM pg_database WHERE datistemplate = false;
```

Deberías ver al menos la base de datos `postgres`. Si no existe, créala:
```sql
CREATE DATABASE postgres;
```

### Paso 6: Crear el esquema 'app' si no existe

Si intentas usar el proyecto Flask pero el esquema no existe, ejecuta:

```sql
CREATE SCHEMA IF NOT EXISTS app;
```

### Paso 7: Probar la conexión desde Python

**Primero, instala las dependencias:**
```powershell
cd Proyecto/backend_flask
pip install -r requirements.txt
```

**Luego, ejecuta el script de prueba:**
```powershell
python test_db_connection.py
```

Este script te dirá exactamente qué está mal con la conexión.

## 🐛 Errores Comunes y Soluciones

### Error: "connection refused" o "could not connect"

**Causa:** PostgreSQL no está corriendo o el puerto es incorrecto.

**Solución:**
1. Verifica que PostgreSQL esté corriendo (Paso 1)
2. Verifica el puerto (Paso 2)
3. Intenta cambiar el puerto en `config.env` a `5432` (puerto por defecto)

### Error: "password authentication failed"

**Causa:** La contraseña en `config.env` es incorrecta.

**Solución:**
1. Verifica la contraseña en `config.env`
2. Si no recuerdas la contraseña, puedes cambiarla:
   - En pgAdmin4: Click derecho en el servidor → **Properties** → **Connection**
   - O desde terminal (si tienes acceso): `psql -U postgres -c "ALTER USER postgres PASSWORD 'nueva_password';"`

### Error: "database does not exist"

**Causa:** La base de datos especificada en `DB_NAME` no existe.

**Solución:**
1. Crea la base de datos en pgAdmin4:
   - Click derecho en **Databases** → **Create** → **Database...**
   - Nombre: `postgres` (o el que uses en `DB_NAME`)
2. O cambia `DB_NAME` en `config.env` a una base de datos que exista

### Error: "schema app does not exist"

**Causa:** El esquema 'app' no ha sido creado todavía.

**Solución:**
1. En pgAdmin4, abre Query Tool
2. Selecciona la base de datos `postgres`
3. Ejecuta: `CREATE SCHEMA IF NOT EXISTS app;`
4. O ejecuta un script SQL completo de inicialización

### Error 500 al ejecutar consultas en pgAdmin4

**Causa:** Puede ser un error interno de pgAdmin4 o un problema con los permisos.

**Solución:**
1. **Reinicia pgAdmin4**
2. **Verifica los logs de PostgreSQL:**
   - En pgAdmin4: Click derecho en el servidor → **Properties** → **Log files**
   - Busca errores recientes
3. **Verifica permisos:**
   ```sql
   GRANT ALL PRIVILEGES ON DATABASE postgres TO postgres;
   GRANT ALL PRIVILEGES ON SCHEMA app TO postgres;
   ```

## 📝 Configuración Recomendada

### Si tienes PostgreSQL en el puerto 5432 (por defecto):

Edita `Proyecto/backend_flask/config.env`:
```env
DB_PORT=5432
```

### Si tienes PostgreSQL en un puerto diferente:

Si tu PostgreSQL está en otro puerto (por ejemplo, 5433), actualiza `config.env`:
```env
DB_PORT=5433
```

## ✅ Checklist de Verificación

- [ ] PostgreSQL está corriendo (verificado en servicios)
- [ ] El puerto en `config.env` coincide con el puerto real de PostgreSQL
- [ ] Las credenciales en `config.env` son correctas
- [ ] La base de datos `postgres` existe
- [ ] Puedo ejecutar consultas simples en pgAdmin4 Query Tool
- [ ] El esquema `app` existe (o está preparado para crearse)
- [ ] Las dependencias de Python están instaladas (`pip install -r requirements.txt`)
- [ ] El script `test_db_connection.py` se ejecuta sin errores

## 🔧 Próximos Pasos

Una vez que la conexión funcione:

1. **Ejecuta el script de inicialización de la base de datos:**
   - En pgAdmin4, abre Query Tool
   - Ejecuta el script SQL que crea todas las tablas
   - O usa el proyecto Flask que crea las tablas automáticamente

2. **Prueba el servidor Flask:**
   ```powershell
   cd Proyecto/backend_flask
   python app.py
   ```

3. **Si todo funciona, deberías ver:**
   ```
   ✅ Conectado a PostgreSQL
   📅 Hora del servidor: ...
   ✅ Servidor Flask ejecutándose en puerto 3001
   ```

## 📞 Información Adicional

Si el problema persiste después de seguir estos pasos, proporciona:

1. El mensaje de error exacto que ves en pgAdmin4
2. La salida del script `test_db_connection.py`
3. Los logs de PostgreSQL (si es posible acceder a ellos)
4. La versión de PostgreSQL que estás usando

Esto ayudará a diagnosticar el problema de manera más específica.


