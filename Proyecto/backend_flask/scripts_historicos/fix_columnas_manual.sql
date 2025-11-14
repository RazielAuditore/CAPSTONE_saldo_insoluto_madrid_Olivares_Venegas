-- Script SQL para verificar y corregir columnas de firma funcionario en app.solicitudes
-- Ejecuta este script directamente en tu base de datos PostgreSQL

-- 1. Verificar si las columnas existen
SELECT column_name, data_type 
FROM information_schema.columns 
WHERE table_schema = 'app' 
AND table_name = 'solicitudes' 
AND column_name IN ('firmado_funcionario', 'fecha_firma_funcionario', 'funcionario_id_firma');

-- 2. Crear las columnas si no existen
ALTER TABLE app.solicitudes 
ADD COLUMN IF NOT EXISTS firmado_funcionario BOOLEAN DEFAULT FALSE;

ALTER TABLE app.solicitudes 
ADD COLUMN IF NOT EXISTS fecha_firma_funcionario TIMESTAMP;

ALTER TABLE app.solicitudes 
ADD COLUMN IF NOT EXISTS funcionario_id_firma INTEGER REFERENCES app.funcionarios(id) ON DELETE SET NULL;

-- 3. Verificar que se crearon correctamente
SELECT column_name, data_type, is_nullable, column_default
FROM information_schema.columns 
WHERE table_schema = 'app' 
AND table_name = 'solicitudes' 
AND column_name IN ('firmado_funcionario', 'fecha_firma_funcionario', 'funcionario_id_firma');

-- 4. Probar un UPDATE manual (reemplaza 1 con un ID de solicitud real)
-- UPDATE app.solicitudes 
-- SET firmado_funcionario = TRUE,
--     fecha_firma_funcionario = NOW(),
--     funcionario_id_firma = 2
-- WHERE id = 1;

-- 5. Verificar el resultado
-- SELECT id, firmado_funcionario, fecha_firma_funcionario, funcionario_id_firma 
-- FROM app.solicitudes 
-- WHERE id = 1;




