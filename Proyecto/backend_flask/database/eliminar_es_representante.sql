-- ============================================
-- Script para eliminar la columna es_representante
-- de la tabla app.beneficiarios
-- ============================================

-- Eliminar la columna es_representante de la tabla beneficiarios
ALTER TABLE app.beneficiarios DROP COLUMN IF EXISTS es_representante;

-- Verificar que la columna fue eliminada
SELECT column_name, data_type 
FROM information_schema.columns 
WHERE table_schema = 'app' 
  AND table_name = 'beneficiarios'
ORDER BY ordinal_position;

