-- ============================================
-- Script de Inicialización de Base de Datos
-- Sistema de Saldo Insoluto
-- ============================================

-- Crear esquema 'app' si no existe
CREATE SCHEMA IF NOT EXISTS app;

-- Establecer el esquema por defecto
SET search_path TO app, public;

-- ============================================
-- TABLA: funcionarios
-- ============================================
CREATE TABLE IF NOT EXISTS app.funcionarios (
    id SERIAL PRIMARY KEY,
    rut VARCHAR(20) UNIQUE NOT NULL,
    nombres VARCHAR(100) NOT NULL,
    apellido_p VARCHAR(100) NOT NULL,
    apellido_m VARCHAR(100),
    email VARCHAR(255) UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    rol VARCHAR(50) DEFAULT 'funcionario',
    sucursal VARCHAR(100),
    iniciales VARCHAR(10),
    activo BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Crear índice en RUT para búsquedas rápidas
CREATE INDEX IF NOT EXISTS idx_funcionarios_rut ON app.funcionarios(rut);
CREATE INDEX IF NOT EXISTS idx_funcionarios_email ON app.funcionarios(email);

-- ============================================
-- TABLA: expediente
-- ============================================
CREATE TABLE IF NOT EXISTS app.expediente (
    id SERIAL PRIMARY KEY,
    expediente_numero VARCHAR(50) UNIQUE NOT NULL,
    estado VARCHAR(50) DEFAULT 'en_proceso',
    observaciones TEXT,
    funcionario_id INTEGER REFERENCES app.funcionarios(id) ON DELETE SET NULL,
    fecha_creacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    fecha_actualizacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Crear índices
CREATE INDEX IF NOT EXISTS idx_expediente_numero ON app.expediente(expediente_numero);
CREATE INDEX IF NOT EXISTS idx_expediente_funcionario ON app.expediente(funcionario_id);
CREATE INDEX IF NOT EXISTS idx_expediente_estado ON app.expediente(estado);

-- ============================================
-- TABLA: representante
-- ============================================
CREATE TABLE IF NOT EXISTS app.representante (
    id SERIAL PRIMARY KEY,
    expediente_id INTEGER NOT NULL REFERENCES app.expediente(id) ON DELETE CASCADE,
    rep_rut VARCHAR(20) UNIQUE NOT NULL,
    rep_calidad VARCHAR(100),
    rep_nombre VARCHAR(100),
    rep_apellido_p VARCHAR(100),
    rep_apellido_m VARCHAR(100),
    rep_telefono VARCHAR(20),
    rep_direccion VARCHAR(255),
    rep_comuna VARCHAR(100),
    rep_region VARCHAR(100),
    rep_email VARCHAR(255),
    creado_en TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    actualizado_en TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Crear índices
CREATE INDEX IF NOT EXISTS idx_representante_expediente ON app.representante(expediente_id);
CREATE INDEX IF NOT EXISTS idx_representante_rut ON app.representante(rep_rut);

-- ============================================
-- TABLA: causante
-- ============================================
CREATE TABLE IF NOT EXISTS app.causante (
    id SERIAL PRIMARY KEY,
    expediente_id INTEGER NOT NULL REFERENCES app.expediente(id) ON DELETE CASCADE,
    fal_run VARCHAR(20) UNIQUE NOT NULL,
    fal_nacionalidad VARCHAR(100),
    fal_nombre VARCHAR(100),
    fal_apellido_p VARCHAR(100),
    fal_apellido_m VARCHAR(100),
    fal_fecha_defuncion DATE,
    fal_comuna_defuncion VARCHAR(100),
    motivo_solicitud TEXT,
    creado_en TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    actualizado_en TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Crear índices
CREATE INDEX IF NOT EXISTS idx_causante_expediente ON app.causante(expediente_id);
CREATE INDEX IF NOT EXISTS idx_causante_run ON app.causante(fal_run);

-- ============================================
-- TABLA: solicitudes
-- ============================================
CREATE TABLE IF NOT EXISTS app.solicitudes (
    id SERIAL PRIMARY KEY,
    expediente_id INTEGER NOT NULL REFERENCES app.expediente(id) ON DELETE CASCADE,
    folio VARCHAR(50) UNIQUE NOT NULL,
    estado VARCHAR(50) DEFAULT 'borrador',
    sucursal VARCHAR(100),
    observacion TEXT,
    representante_rut VARCHAR(20) REFERENCES app.representante(rep_rut),
    causante_rut VARCHAR(20) REFERENCES app.causante(fal_run),
    fecha_defuncion DATE,
    comuna_fallecimiento VARCHAR(100),
    fecha_creacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    fecha_actualizacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Crear índices
CREATE INDEX IF NOT EXISTS idx_solicitudes_expediente ON app.solicitudes(expediente_id);
CREATE INDEX IF NOT EXISTS idx_solicitudes_folio ON app.solicitudes(folio);
CREATE INDEX IF NOT EXISTS idx_solicitudes_estado ON app.solicitudes(estado);

-- ============================================
-- TABLA: beneficiarios
-- ============================================
CREATE TABLE IF NOT EXISTS app.beneficiarios (
    id SERIAL PRIMARY KEY,
    expediente_id INTEGER NOT NULL REFERENCES app.expediente(id) ON DELETE CASCADE,
    solicitud_id INTEGER REFERENCES app.solicitudes(id) ON DELETE CASCADE,
    ben_nombre VARCHAR(255) NOT NULL,
    ben_run VARCHAR(20) NOT NULL,
    ben_parentesco VARCHAR(100),
    es_representante BOOLEAN DEFAULT false,
    creado_en TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    actualizado_en TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(expediente_id, ben_run)
);

-- Crear índices
CREATE INDEX IF NOT EXISTS idx_beneficiarios_expediente ON app.beneficiarios(expediente_id);
CREATE INDEX IF NOT EXISTS idx_beneficiarios_solicitud ON app.beneficiarios(solicitud_id);
CREATE INDEX IF NOT EXISTS idx_beneficiarios_run ON app.beneficiarios(ben_run);

-- ============================================
-- TABLA: documentos_saldo_insoluto
-- ============================================
CREATE TABLE IF NOT EXISTS app.documentos_saldo_insoluto (
    id SERIAL PRIMARY KEY,
    expediente_id INTEGER NOT NULL REFERENCES app.expediente(id) ON DELETE CASCADE,
    solicitud_id INTEGER REFERENCES app.solicitudes(id) ON DELETE CASCADE,
    doc_tipo_id INTEGER DEFAULT 1,
    doc_nombre_archivo VARCHAR(255) NOT NULL,
    doc_archivo_blob BYTEA,
    doc_mime_type VARCHAR(100),
    doc_tamano_bytes BIGINT,
    doc_sha256 VARCHAR(64),
    doc_ruta_storage VARCHAR(500),
    doc_observaciones TEXT,
    doc_estado VARCHAR(50) DEFAULT 'pendiente',
    doc_fecha_subida TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Crear índices
CREATE INDEX IF NOT EXISTS idx_documentos_expediente ON app.documentos_saldo_insoluto(expediente_id);
CREATE INDEX IF NOT EXISTS idx_documentos_solicitud ON app.documentos_saldo_insoluto(solicitud_id);
CREATE INDEX IF NOT EXISTS idx_documentos_sha256 ON app.documentos_saldo_insoluto(doc_sha256);

-- ============================================
-- TABLA: validacion
-- ============================================
CREATE TABLE IF NOT EXISTS app.validacion (
    id SERIAL PRIMARY KEY,
    expediente_id INTEGER NOT NULL REFERENCES app.expediente(id) ON DELETE CASCADE,
    solicitud_id INTEGER NOT NULL REFERENCES app.solicitudes(id) ON DELETE CASCADE,
    val_sucursal VARCHAR(100),
    val_estado VARCHAR(50) DEFAULT 'pendiente',
    val_firma_representante JSONB,
    val_firma_funcionario JSONB,
    val_fecha_firma_funcionario TIMESTAMP,
    creado_en TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    actualizado_en TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Crear índices
CREATE INDEX IF NOT EXISTS idx_validacion_expediente ON app.validacion(expediente_id);
CREATE INDEX IF NOT EXISTS idx_validacion_solicitud ON app.validacion(solicitud_id);
CREATE INDEX IF NOT EXISTS idx_validacion_estado ON app.validacion(val_estado);

-- ============================================
-- TABLA: usuarios_firma
-- ============================================
CREATE TABLE IF NOT EXISTS app.usuarios_firma (
    id SERIAL PRIMARY KEY,
    rut VARCHAR(20) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    activo BOOLEAN DEFAULT true,
    creado_en TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    actualizado_en TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Crear índice
CREATE INDEX IF NOT EXISTS idx_usuarios_firma_rut ON app.usuarios_firma(rut);

-- ============================================
-- TABLA: firmas_beneficiarios
-- ============================================
CREATE TABLE IF NOT EXISTS app.firmas_beneficiarios (
    id SERIAL PRIMARY KEY,
    expediente_id INTEGER NOT NULL REFERENCES app.expediente(id) ON DELETE CASCADE,
    beneficiario_id INTEGER NOT NULL REFERENCES app.beneficiarios(id) ON DELETE CASCADE,
    firma_hash VARCHAR(255) NOT NULL,
    fecha_firma TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    estado VARCHAR(50) DEFAULT 'activa',
    observaciones TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Crear índices
CREATE INDEX IF NOT EXISTS idx_firmas_beneficiarios_expediente ON app.firmas_beneficiarios(expediente_id);
CREATE INDEX IF NOT EXISTS idx_firmas_beneficiarios_beneficiario ON app.firmas_beneficiarios(beneficiario_id);
CREATE INDEX IF NOT EXISTS idx_firmas_beneficiarios_estado ON app.firmas_beneficiarios(estado);

-- Crear índice único para evitar firmas duplicadas
CREATE UNIQUE INDEX IF NOT EXISTS idx_firmas_beneficiarios_unique 
ON app.firmas_beneficiarios(expediente_id, beneficiario_id) 
WHERE estado = 'activa';

-- ============================================
-- TRIGGERS para actualizar timestamps
-- ============================================

-- Función para actualizar fecha_actualizacion
CREATE OR REPLACE FUNCTION app.update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.actualizado_en = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Trigger para expediente
DROP TRIGGER IF EXISTS update_expediente_updated_at ON app.expediente;
CREATE TRIGGER update_expediente_updated_at
    BEFORE UPDATE ON app.expediente
    FOR EACH ROW
    EXECUTE FUNCTION app.update_updated_at_column();

-- Trigger para representante
DROP TRIGGER IF EXISTS update_representante_updated_at ON app.representante;
CREATE TRIGGER update_representante_updated_at
    BEFORE UPDATE ON app.representante
    FOR EACH ROW
    EXECUTE FUNCTION app.update_updated_at_column();

-- Trigger para causante
DROP TRIGGER IF EXISTS update_causante_updated_at ON app.causante;
CREATE TRIGGER update_causante_updated_at
    BEFORE UPDATE ON app.causante
    FOR EACH ROW
    EXECUTE FUNCTION app.update_updated_at_column();

-- Trigger para solicitudes
DROP TRIGGER IF EXISTS update_solicitudes_updated_at ON app.solicitudes;
CREATE TRIGGER update_solicitudes_updated_at
    BEFORE UPDATE ON app.solicitudes
    FOR EACH ROW
    EXECUTE FUNCTION app.update_updated_at_column();

-- Trigger para beneficiarios
DROP TRIGGER IF EXISTS update_beneficiarios_updated_at ON app.beneficiarios;
CREATE TRIGGER update_beneficiarios_updated_at
    BEFORE UPDATE ON app.beneficiarios
    FOR EACH ROW
    EXECUTE FUNCTION app.update_updated_at_column();

-- Trigger para validacion
DROP TRIGGER IF EXISTS update_validacion_updated_at ON app.validacion;
CREATE TRIGGER update_validacion_updated_at
    BEFORE UPDATE ON app.validacion
    FOR EACH ROW
    EXECUTE FUNCTION app.update_updated_at_column();

-- Trigger para usuarios_firma
DROP TRIGGER IF EXISTS update_usuarios_firma_updated_at ON app.usuarios_firma;
CREATE TRIGGER update_usuarios_firma_updated_at
    BEFORE UPDATE ON app.usuarios_firma
    FOR EACH ROW
    EXECUTE FUNCTION app.update_updated_at_column();

-- Trigger para firmas_beneficiarios
DROP TRIGGER IF EXISTS update_firmas_beneficiarios_updated_at ON app.firmas_beneficiarios;
CREATE TRIGGER update_firmas_beneficiarios_updated_at
    BEFORE UPDATE ON app.firmas_beneficiarios
    FOR EACH ROW
    EXECUTE FUNCTION app.update_updated_at_column();

-- ============================================
-- DATOS INICIALES
-- ============================================

-- Insertar funcionario administrador por defecto
-- La contraseña es 'admin123' hasheada con bcrypt
-- Para generar un nuevo hash, usa: python -c "import bcrypt; print(bcrypt.hashpw('tu_password'.encode('utf-8'), bcrypt.gensalt()).decode('utf-8'))"
INSERT INTO app.funcionarios (rut, nombres, apellido_p, password_hash, rol, sucursal, iniciales, email)
VALUES (
    '12345678-9',
    'Admin',
    'Sistema',
    '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewY5GyYp7QxqN3KO', -- admin123
    'administrador',
    'Central',
    'AS',
    'admin@sistema.cl'
)
ON CONFLICT (rut) DO NOTHING;

-- ============================================
-- PERMISOS
-- ============================================

-- Otorgar permisos al usuario postgres (o el usuario que uses)
-- Ajusta según tu configuración
GRANT ALL PRIVILEGES ON SCHEMA app TO postgres;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA app TO postgres;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA app TO postgres;

-- ============================================
-- FIN DEL SCRIPT
-- ============================================

-- Verificar tablas creadas
SELECT 
    table_schema,
    table_name
FROM information_schema.tables
WHERE table_schema = 'app'
ORDER BY table_name;

-- Mensaje de confirmación
DO $$
BEGIN
    RAISE NOTICE '✅ Base de datos inicializada correctamente';
    RAISE NOTICE '✅ Esquema app creado';
    RAISE NOTICE '✅ Todas las tablas creadas';
    RAISE NOTICE '✅ Triggers configurados';
    RAISE NOTICE '✅ Usuario administrador creado (RUT: 12345678-9, Password: admin123)';
END $$;


