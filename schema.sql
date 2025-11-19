-- Script para crear las tablas necesarias
-- Ejecutar este script en PostgreSQL antes de usar la API

-- Tabla de usuarios para autenticación JWT
CREATE TABLE IF NOT EXISTS usuarios (
    id SERIAL PRIMARY KEY,
    username VARCHAR(50) NOT NULL UNIQUE,
    email VARCHAR(255) NOT NULL UNIQUE,
    hashed_password VARCHAR(255) NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Índices para usuarios
CREATE INDEX IF NOT EXISTS idx_usuarios_username ON usuarios(username);
CREATE INDEX IF NOT EXISTS idx_usuarios_email ON usuarios(email);

-- Tabla de productos
CREATE TABLE IF NOT EXISTS productos (
    id SERIAL PRIMARY KEY,
    nombre VARCHAR(255) NOT NULL UNIQUE,  -- REGLA DE NEGOCIO: Unicidad de nombre
    descripcion TEXT,
    estado VARCHAR(20) NOT NULL CHECK (estado IN ('activo', 'descontinuado')),
    fecha_entrada DATE NOT NULL,
    nivel_minimo_stock INTEGER NOT NULL CHECK (nivel_minimo_stock > 0),
    proveedor_id INTEGER NOT NULL,
    impuesto_id INTEGER NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Índices para mejorar el rendimiento
CREATE INDEX IF NOT EXISTS idx_productos_estado ON productos(estado);
CREATE INDEX IF NOT EXISTS idx_productos_proveedor ON productos(proveedor_id);

-- Comentarios en la tabla
COMMENT ON TABLE productos IS 'Tabla para almacenar información de productos';
COMMENT ON COLUMN productos.estado IS 'Estado del producto: activo o descontinuado';
COMMENT ON COLUMN productos.nivel_minimo_stock IS 'Nivel mínimo de stock permitido';

