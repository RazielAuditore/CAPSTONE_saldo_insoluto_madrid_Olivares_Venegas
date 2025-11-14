-- Script para agregar 'rechazado' y 'rechazado/enRevision' al ENUM app.estado_solicitud

-- Agregar 'rechazado' si no existe
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_enum 
        WHERE enumlabel = 'rechazado' 
        AND enumtypid = (SELECT oid FROM pg_type WHERE typname = 'estado_solicitud' AND typnamespace = (SELECT oid FROM pg_namespace WHERE nspname = 'app'))
    ) THEN
        ALTER TYPE app.estado_solicitud ADD VALUE 'rechazado';
        RAISE NOTICE 'rechazado agregado al ENUM';
    ELSE
        RAISE NOTICE 'rechazado ya existe en el ENUM';
    END IF;
END $$;

-- Agregar 'rechazado/enRevision' si no existe
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_enum 
        WHERE enumlabel = 'rechazado/enRevision' 
        AND enumtypid = (SELECT oid FROM pg_type WHERE typname = 'estado_solicitud' AND typnamespace = (SELECT oid FROM pg_namespace WHERE nspname = 'app'))
    ) THEN
        ALTER TYPE app.estado_solicitud ADD VALUE 'rechazado/enRevision';
        RAISE NOTICE 'rechazado/enRevision agregado al ENUM';
    ELSE
        RAISE NOTICE 'rechazado/enRevision ya existe en el ENUM';
    END IF;
END $$;

-- Verificar valores finales
SELECT unnest(enum_range(NULL::app.estado_solicitud)) AS valor
ORDER BY valor;

