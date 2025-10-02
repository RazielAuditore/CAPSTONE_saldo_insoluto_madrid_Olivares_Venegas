const express = require('express');
const cors = require('cors');
require('dotenv').config({ path: './config.env' });

const { testConnection, createTables } = require('./database');

const app = express();
const PORT = process.env.PORT || 3000;

// Middleware básico
app.use(cors());
app.use(express.json());

// Ruta de prueba
app.get('/', (req, res) => {
  res.json({
    message: 'Backend del Sistema de Saldo Insoluto',
    status: 'OK',
    timestamp: new Date().toISOString()
  });
});

// Ruta de salud
app.get('/health', (req, res) => {
  res.json({
    status: 'OK',
    database: 'PostgreSQL',
    port: PORT
  });
});

// Inicializar servidor
async function startServer() {
  try {
    console.log('🚀 Iniciando servidor...');
    
    // Probar conexión a PostgreSQL
    const connected = await testConnection();
    if (!connected) {
      console.log('⚠️  Continuando sin base de datos...');
    } else {
      // Crear tablas si la conexión es exitosa
      await createTables();
    }
    
    // Iniciar servidor
    app.listen(PORT, () => {
      console.log(`✅ Servidor ejecutándose en puerto ${PORT}`);
      console.log(`🔗 URL: http://localhost:${PORT}`);
    });
    
  } catch (error) {
    console.error('❌ Error al iniciar el servidor:', error);
    process.exit(1);
  }
}

startServer();
