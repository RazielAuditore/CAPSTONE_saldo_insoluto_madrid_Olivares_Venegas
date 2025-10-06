const { Pool } = require('pg');
require('dotenv').config({ path: './config.env' });

// Configuración de la base de datos
const pool = new Pool({
  user: process.env.DB_USER || 'postgres',
  host: process.env.DB_HOST || 'localhost',
  database: process.env.DB_NAME || 'postgres',
  password: process.env.DB_PASSWORD || '1234',
  port: process.env.DB_PORT || 5433,
  searchPath: 'app, public', // Usar esquema app primero
});

// Función para probar la conexión
async function testConnection() {
  const client = await pool.connect();
  
  try {
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

module.exports = {
  pool,
  testConnection
};