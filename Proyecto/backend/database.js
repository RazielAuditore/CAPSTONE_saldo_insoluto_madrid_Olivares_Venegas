const { Pool } = require('pg');
require('dotenv').config({ path: './config.env' });

// Configuración de la conexión a PostgreSQL
const pool = new Pool({
  host: process.env.DB_HOST || '127.0.0.1',
  port: process.env.DB_PORT || 5433,
  database: process.env.DB_NAME || 'postgres',
  user: process.env.DB_USER || 'postgres',
  password: process.env.DB_PASSWORD,
  max: 20,
  idleTimeoutMillis: 30000,
  connectionTimeoutMillis: 2000,
});

// Función para probar la conexión
async function testConnection() {
  try {
    const client = await pool.connect();
    console.log('✅ Conectado a PostgreSQL');
    
    // Probar con una consulta simple
    const result = await client.query('SELECT NOW()');
    console.log('📅 Hora del servidor:', result.rows[0].now);
    
    client.release();
    return true;
  } catch (error) {
    console.error('❌ Error conectando a PostgreSQL:', error.message);
    return false;
  }
}

// Función para crear las tablas básicas
async function createTables() {
  const client = await pool.connect();
  
  try {
    console.log('🔨 Creando tablas...');
    
    // Tabla de representantes
    await client.query(`
      CREATE TABLE IF NOT EXISTS representantes (
        id SERIAL PRIMARY KEY,
        rut VARCHAR(12) UNIQUE NOT NULL,
        nombres VARCHAR(100) NOT NULL,
        ap_paterno VARCHAR(100) NOT NULL,
        ap_materno VARCHAR(100),
        telefono VARCHAR(20),
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
      )
    `);
    console.log('✅ Tabla representantes creada');

    // Tabla de fallecidos
    await client.query(`
      CREATE TABLE IF NOT EXISTS fallecidos (
        id SERIAL PRIMARY KEY,
        rut VARCHAR(12) UNIQUE NOT NULL,
        nombres VARCHAR(100) NOT NULL,
        ap_paterno VARCHAR(100) NOT NULL,
        ap_materno VARCHAR(100),
        fecha_defuncion DATE,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
      )
    `);
    console.log('✅ Tabla fallecidos creada');

    // Tabla de solicitudes
    await client.query(`
      CREATE TABLE IF NOT EXISTS solicitudes (
        id SERIAL PRIMARY KEY,
        representante_id INTEGER REFERENCES representantes(id),
        fallecido_id INTEGER REFERENCES fallecidos(id),
        estado VARCHAR(50) DEFAULT 'pendiente',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
      )
    `);
    console.log('✅ Tabla solicitudes creada');
    
  } catch (error) {
    console.error('❌ Error creando tablas:', error.message);
    throw error;
  } finally {
    client.release();
  }
}

module.exports = {
  pool,
  testConnection,
  createTables
};
