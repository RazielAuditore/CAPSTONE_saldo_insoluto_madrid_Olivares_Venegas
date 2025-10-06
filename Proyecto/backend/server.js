const express = require('express');
const cors = require('cors');
const multer = require('multer');
const path = require('path');
const fs = require('fs');
require('dotenv').config({ path: './config.env' });

const { pool, testConnection } = require('./database');

const app = express();
const PORT = process.env.PORT || 8000;

// Configuración de multer para subida de archivos
const storage = multer.diskStorage({
  destination: function (req, file, cb) {
    const uploadDir = 'uploads/';
    if (!fs.existsSync(uploadDir)) {
      fs.mkdirSync(uploadDir, { recursive: true });
    }
    cb(null, uploadDir);
  },
  filename: function (req, file, cb) {
    const uniqueSuffix = Date.now() + '-' + Math.round(Math.random() * 1E9);
    cb(null, file.fieldname + '-' + uniqueSuffix + path.extname(file.originalname));
  }
});

const upload = multer({ 
  storage: storage,
  limits: {
    fileSize: 10 * 1024 * 1024 // 10MB límite
  },
  fileFilter: function (req, file, cb) {
    const allowedTypes = /jpeg|jpg|png|pdf|doc|docx/;
    const extname = allowedTypes.test(path.extname(file.originalname).toLowerCase());
    const mimetype = allowedTypes.test(file.mimetype);
    
    if (mimetype && extname) {
      return cb(null, true);
    } else {
      cb(new Error('Solo se permiten archivos: JPEG, JPG, PNG, PDF, DOC, DOCX'));
    }
  }
});

// Middleware básico
app.use(express.json());
app.use(express.urlencoded({ extended: true }));
app.use('/uploads', express.static('uploads'));

// CORS
app.use(cors({
  origin: ['http://localhost:8080', 'http://127.0.0.1:8080'],
  credentials: true,
  methods: ['GET', 'POST', 'PUT', 'DELETE', 'OPTIONS'],
  allowedHeaders: ['Content-Type', 'Authorization']
}));

// Ruta básica de prueba
app.get('/', (req, res) => {
  res.json({ 
    message: 'Servidor Saldo Insoluto funcionando',
    status: 'OK',
    timestamp: new Date().toISOString()
  });
});

// Ruta de salud del servidor
app.get('/api/health', (req, res) => {
  res.json({ 
    status: 'OK',
    message: 'Servidor funcionando correctamente',
    timestamp: new Date().toISOString()
  });
});

// Obtener tipos de documentos
app.get('/api/tipos-documentos', async (req, res) => {
  try {
    const result = await pool.query('SELECT * FROM app.doc_tipos ORDER BY id');
    res.json({
      success: true,
      data: result.rows
    });
  } catch (error) {
    console.error('Error obteniendo tipos de documentos:', error);
    res.status(500).json({
      success: false,
      message: 'Error interno del servidor'
    });
  }
});

// Crear nueva solicitud de saldo insoluto
app.post('/api/solicitudes', async (req, res) => {
  const client = await pool.connect();
  
  try {
    await client.query('BEGIN');
    
    // 1. Crear expediente principal
    const expedienteNumero = `EXP-${new Date().getFullYear()}-${Date.now().toString().slice(-6)}`;
    const expedienteQuery = `
      INSERT INTO app.expediente (expediente_numero, estado, observaciones)
      VALUES ($1, 'en_proceso', 'Expediente de saldo insoluto creado automáticamente')
      RETURNING id
    `;
    
    const expedienteResult = await client.query(expedienteQuery, [expedienteNumero]);
    const expedienteId = expedienteResult.rows[0].id;
    
    // Datos del formulario
    const {
      // Datos del representante
      rep_nombre, rep_run, rep_calidad, rep_apellido_p, rep_apellido_m, rep_direccion, rep_comuna, rep_region, rep_telefono, rep_email,
      // Datos del fallecido
      fal_nombre, fal_run, fal_nacionalidad, fal_apellido_p, fal_apellido_m, fal_fecha_defuncion, fal_comuna_defuncion,
      // Datos de la solicitud
      monto_solicitado, motivo_solicitud, sucursal,
      // Datos de beneficiarios
      beneficiarios,
      // Tipos de documentos
      tipo_documento
    } = req.body;
    
    // Debug: Mostrar los datos recibidos
    console.log('🔍 Datos recibidos del frontend:');
    console.log('  fal_fecha_defuncion:', fal_fecha_defuncion);
    console.log('  fal_comuna_defuncion:', fal_comuna_defuncion);
    console.log('  fal_nombre:', fal_nombre);
    console.log('  fal_run:', fal_run);
    
    // 2. Crear representante en tabla específica
    const representanteQuery = `
      INSERT INTO app.representante (expediente_id, rep_rut, rep_calidad, rep_nombre, rep_apellido_p, rep_apellido_m, rep_telefono, rep_direccion, rep_comuna, rep_region, rep_email)
      VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
      RETURNING rep_rut
    `;
    
    const representanteResult = await client.query(representanteQuery, [
      expedienteId,
      rep_run || null, 
      rep_calidad || null,
      rep_nombre || null, 
      rep_apellido_p || null,
      rep_apellido_m || null,
      rep_telefono || null, 
      rep_direccion || null, 
      rep_comuna || null, 
      rep_region || null,
      rep_email || null
    ]);
    const representanteRut = representanteResult.rows[0].rep_rut;
    
    // 3. Crear causante en tabla específica
    const causanteQuery = `
      INSERT INTO app.causante (expediente_id, fal_run, fal_nacionalidad, fal_nombre, fal_apellido_p, fal_apellido_m, fal_fecha_defuncion, fal_comuna_defuncion, motivo_solicitud)
      VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
      RETURNING fal_run
    `;
    
    const causanteResult = await client.query(causanteQuery, [
      expedienteId,
      fal_run || null, 
      fal_nacionalidad || null,
      fal_nombre || null, 
      fal_apellido_p || null,
      fal_apellido_m || null,
      fal_fecha_defuncion || null, 
      fal_comuna_defuncion || null,
      motivo_solicitud || null
    ]);
    const causanteRun = causanteResult.rows[0].fal_run;
    
    // 4. Crear solicitud
    const folio = `SI-${Date.now()}-${Math.random().toString(36).substr(2, 4).toUpperCase()}`;
    const solicitudQuery = `
      INSERT INTO app.solicitudes (expediente_id, folio, estado, sucursal, observacion, representante_rut, causante_rut, fecha_defuncion, comuna_fallecimiento)
      VALUES ($1, $2, 'borrador', $3, $4, $5, $6, $7, $8)
      RETURNING id
    `;
    
    const solicitudResult = await client.query(solicitudQuery, [
      expedienteId, folio, sucursal, motivo_solicitud || null, representanteRut, causanteRun, fal_fecha_defuncion || null, fal_comuna_defuncion || null
    ]);
    const solicitudId = solicitudResult.rows[0].id;
    
    // 5. Crear beneficiarios en tabla específica
    if (beneficiarios && Array.isArray(beneficiarios)) {
      for (const beneficiario of beneficiarios) {
        if (beneficiario.nombre && beneficiario.run) {
          const beneficiarioQuery = `
            INSERT INTO app.beneficiarios (expediente_id, solicitud_id, ben_nombre, ben_run, ben_parentesco, es_representante)
            VALUES ($1, $2, $3, $4, $5, $6)
            RETURNING id
          `;
          
          await client.query(beneficiarioQuery, [
            expedienteId,
            solicitudId, 
            beneficiario.nombre, 
            beneficiario.run, 
            beneficiario.parentesco || null,
            beneficiario.es_representante || false
          ]);
        }
      }
    }
    
    // 6. Insertar documentos
    if (tipo_documento && Array.isArray(tipo_documento)) {
      for (let i = 0; i < tipo_documento.length; i++) {
        const tipoDoc = tipo_documento[i];
        if (tipoDoc && tipoDoc !== '') {
          const documentoQuery = `
            INSERT INTO app.documentos_saldo_insoluto (expediente_id, solicitud_id, doc_tipo_id, doc_nombre_archivo, doc_estado)
            VALUES ($1, $2, $3, $4, 'pendiente')
            RETURNING id
          `;
          
          await client.query(documentoQuery, [
            expedienteId,
            solicitudId, 
            parseInt(tipoDoc), 
            `documento_${i + 1}_tipo_${tipoDoc}`
          ]);
        }
      }
    }
    
    // 7. Crear registro de validación
    const validacionQuery = `
      INSERT INTO app.validacion (expediente_id, solicitud_id, val_sucursal, val_estado)
      VALUES ($1, $2, $3, 'pendiente')
      RETURNING id
    `;
    
    await client.query(validacionQuery, [
      expedienteId,
      solicitudId, 
      sucursal || null
    ]);
    
    await client.query('COMMIT');
    
    res.json({
      success: true,
      message: 'Expediente creado exitosamente',
      expediente_id: expedienteId,
      expediente_numero: expedienteNumero,
      solicitud_id: solicitudId,
      folio: folio
    });
    
  } catch (error) {
    await client.query('ROLLBACK');
    console.error('Error creando solicitud:', error);
    res.status(500).json({
      success: false,
      message: 'Error interno del servidor',
      error: error.message
    });
  } finally {
    client.release();
  }
});

// Obtener todas las solicitudes
app.get('/api/solicitudes', async (req, res) => {
  try {
    const result = await pool.query(`
      SELECT s.*, 
             r.nombres as rep_nombre, r.rut as rep_rut,
             c.nombres as causante_nombre, c.rut as causante_rut,
             COUNT(DISTINCT sb.beneficiario_id) as total_beneficiarios,
             COUNT(DISTINCT d.id) as total_documentos
      FROM solicitudes s
      LEFT JOIN personas r ON s.representante_id = r.id
      LEFT JOIN personas c ON s.causante_id = c.id
      LEFT JOIN solicitud_beneficiarios sb ON s.id = sb.solicitud_id
      LEFT JOIN documentos d ON s.id = d.solicitud_id
      GROUP BY s.id, r.nombres, r.rut, c.nombres, c.rut
      ORDER BY s.creado_en DESC
    `);
    
    res.json({
      success: true,
      data: result.rows
    });
  } catch (error) {
    console.error('Error obteniendo solicitudes:', error);
    res.status(500).json({
      success: false,
      message: 'Error interno del servidor'
    });
  }
});

// Obtener expediente completo por ID
app.get('/api/expediente/:id', async (req, res) => {
  try {
    const { id } = req.params;
    
    // Obtener expediente
    const expedienteResult = await pool.query(`
      SELECT * FROM app.expediente WHERE id = $1
    `, [id]);
    
    if (expedienteResult.rows.length === 0) {
      return res.status(404).json({
        success: false,
        message: 'Expediente no encontrado'
      });
    }
    
    const expediente = expedienteResult.rows[0];
    
    // Obtener representante
    const representanteResult = await pool.query(`
      SELECT * FROM app.representante WHERE expediente_id = $1
    `, [id]);
    
    // Obtener causante
    const causanteResult = await pool.query(`
      SELECT * FROM app.causante WHERE expediente_id = $1
    `, [id]);
    
    // Obtener solicitudes
    const solicitudesResult = await pool.query(`
      SELECT * FROM app.solicitudes WHERE expediente_id = $1
    `, [id]);
    
    // Obtener beneficiarios
    const beneficiariosResult = await pool.query(`
      SELECT * FROM app.beneficiarios WHERE expediente_id = $1
    `, [id]);
    
    // Obtener documentos
    const documentosResult = await pool.query(`
      SELECT d.*, dt.nombre as tipo_documento_nombre, dt.codigo as tipo_codigo
      FROM app.documentos_saldo_insoluto d
      LEFT JOIN app.doc_tipos dt ON d.doc_tipo_id = dt.id
      WHERE d.expediente_id = $1
    `, [id]);
    
    // Obtener validación
    const validacionResult = await pool.query(`
      SELECT * FROM app.validacion WHERE expediente_id = $1
    `, [id]);
    
    res.json({
      success: true,
      data: {
        expediente: expediente,
        representante: representanteResult.rows[0] || null,
        causante: causanteResult.rows[0] || null,
        solicitudes: solicitudesResult.rows,
        beneficiarios: beneficiariosResult.rows,
        documentos: documentosResult.rows,
        validacion: validacionResult.rows[0] || null
      }
    });
  } catch (error) {
    console.error('Error obteniendo expediente:', error);
    res.status(500).json({
      success: false,
      message: 'Error interno del servidor'
    });
  }
});

// Obtener solicitud por ID
app.get('/api/solicitudes/:id', async (req, res) => {
  try {
    const { id } = req.params;
    
    // Obtener solicitud con datos de personas
    const solicitudResult = await pool.query(`
      SELECT s.*, 
             r.nombres as rep_nombre, r.rut as rep_rut, r.telefono as rep_telefono, 
             r.email as rep_email, r.domicilio as rep_domicilio, r.comuna as rep_comuna, r.region as rep_region,
             c.nombres as causante_nombre, c.rut as causante_rut, c.domicilio as causante_domicilio,
             c.comuna as causante_comuna, c.region as causante_region
      FROM solicitudes s
      LEFT JOIN personas r ON s.representante_id = r.id
      LEFT JOIN personas c ON s.causante_id = c.id
      WHERE s.id = $1
    `, [id]);
    
    if (solicitudResult.rows.length === 0) {
      return res.status(404).json({
        success: false,
        message: 'Solicitud no encontrada'
      });
    }
    
    // Obtener beneficiarios
    const beneficiariosResult = await pool.query(`
      SELECT p.nombres, p.rut, sb.parentesco, sb.es_representante, sb.porcentaje
      FROM solicitud_beneficiarios sb
      LEFT JOIN personas p ON sb.beneficiario_id = p.id
      WHERE sb.solicitud_id = $1
    `, [id]);
    
    // Obtener documentos
    const documentosResult = await pool.query(`
      SELECT d.*, dt.nombre as tipo_documento_nombre, dt.codigo as tipo_codigo
      FROM documentos d
      LEFT JOIN doc_tipos dt ON d.tipo_id = dt.id
      WHERE d.solicitud_id = $1
    `, [id]);
    
    // Obtener firmas
    const firmasResult = await pool.query(`
      SELECT f.*, p.nombres as firmante_nombre, p.rut as firmante_rut
      FROM firmas f
      LEFT JOIN personas p ON f.firmante_id = p.id
      WHERE f.solicitud_id = $1
    `, [id]);
    
    res.json({
      success: true,
      data: {
        solicitud: solicitudResult.rows[0],
        beneficiarios: beneficiariosResult.rows,
        documentos: documentosResult.rows,
        firmas: firmasResult.rows
      }
    });
  } catch (error) {
    console.error('Error obteniendo solicitud:', error);
    res.status(500).json({
      success: false,
      message: 'Error interno del servidor'
    });
  }
});

// Actualizar estado de solicitud
app.put('/api/solicitudes/:id/estado', async (req, res) => {
  try {
    const { id } = req.params;
    const { estado } = req.body;
    
    const validStates = ['borrador', 'firmas_pend', 'firmas_ok', 'enviada', 'cerrada', 'rechazada'];
    if (!validStates.includes(estado)) {
      return res.status(400).json({
        success: false,
        message: 'Estado inválido'
      });
    }
    
    const result = await pool.query(
      'UPDATE solicitudes SET estado = $1, actualizado_en = now() WHERE id = $2 RETURNING *',
      [estado, id]
    );
    
    if (result.rows.length === 0) {
      return res.status(404).json({
        success: false,
        message: 'Solicitud no encontrada'
      });
    }
    
    res.json({
      success: true,
      message: 'Estado actualizado exitosamente',
      data: result.rows[0]
    });
  } catch (error) {
    console.error('Error actualizando estado:', error);
    res.status(500).json({
      success: false,
      message: 'Error interno del servidor'
    });
  }
});

// Actualizar firma del representante
app.post('/api/solicitudes/:id/firma-representante', async (req, res) => {
  try {
    const { id } = req.params;
    const { firma_data } = req.body;
    
    const result = await pool.query(`
      UPDATE app.validacion 
      SET val_firma_representante = $1, actualizado_en = now()
      WHERE solicitud_id = $2
      RETURNING *
    `, [JSON.stringify(firma_data), id]);
    
    if (result.rows.length === 0) {
      return res.status(404).json({
        success: false,
        message: 'Solicitud no encontrada'
      });
    }
    
    res.json({
      success: true,
      message: 'Firma del representante guardada exitosamente',
      data: result.rows[0]
    });
  } catch (error) {
    console.error('Error guardando firma del representante:', error);
    res.status(500).json({
      success: false,
      message: 'Error interno del servidor'
    });
  }
});

// Actualizar firma del funcionario
app.post('/api/solicitudes/:id/firma-funcionario', async (req, res) => {
  try {
    const { id } = req.params;
    const { firma_data } = req.body;
    
    const result = await pool.query(`
      UPDATE app.validacion 
      SET val_firma_funcionario = $1, actualizado_en = now()
      WHERE solicitud_id = $2
      RETURNING *
    `, [JSON.stringify(firma_data), id]);
    
    if (result.rows.length === 0) {
      return res.status(404).json({
        success: false,
        message: 'Solicitud no encontrada'
      });
    }
    
    res.json({
      success: true,
      message: 'Firma del funcionario guardada exitosamente',
      data: result.rows[0]
    });
  } catch (error) {
    console.error('Error guardando firma del funcionario:', error);
    res.status(500).json({
      success: false,
      message: 'Error interno del servidor'
    });
  }
});

// Obtener estadísticas
app.get('/api/estadisticas', async (req, res) => {
  try {
    const stats = await pool.query(`
      SELECT 
        estado,
        COUNT(*) as cantidad
      FROM solicitudes 
      GROUP BY estado
      ORDER BY cantidad DESC
    `);
    
    const totalDocs = await pool.query('SELECT COUNT(*) as total FROM documentos');
    const totalPersonas = await pool.query('SELECT COUNT(*) as total FROM personas');
    
    res.json({
      success: true,
      data: {
        solicitudes_por_estado: stats.rows,
        total_documentos: parseInt(totalDocs.rows[0].total),
        total_personas: parseInt(totalPersonas.rows[0].total)
      }
    });
  } catch (error) {
    console.error('Error obteniendo estadísticas:', error);
    res.status(500).json({
      success: false,
      message: 'Error interno del servidor'
    });
  }
});

// Función para iniciar el servidor
async function startServer() {
  try {
    console.log('🚀 Iniciando servidor...');
    
    // Probar conexión a la base de datos
    const connected = await testConnection();
    if (!connected) {
      console.log('⚠️  Continuando sin conexión a base de datos...');
    }
    
    // Iniciar servidor
    app.listen(PORT, () => {
      console.log(`✅ Servidor ejecutándose en puerto ${PORT}`);
      console.log(`🔗 URL: http://localhost:${PORT}`);
    });
    
  } catch (error) {
    console.error('❌ Error iniciando servidor:', error);
    process.exit(1);
  }
}

// Iniciar servidor
startServer();