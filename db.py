import os
import psycopg2
from psycopg2 import pool
from dotenv import load_dotenv
import logging

load_dotenv()

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# POOL DE CONEXIONES
connection_pool = None

def init_connection_pool():
    """Inicializa el pool de conexiones"""
    global connection_pool
    try:
        connection_pool = psycopg2.pool.SimpleConnectionPool(
            minconn=1,  # Mínimo de conexiones en el pool
            maxconn=10,  # Máximo de conexiones en el pool
            host=os.getenv("DB_HOST"),
            port=os.getenv("DB_PORT"),
            dbname=os.getenv("DB_NAME"),
            user=os.getenv("DB_USER"),
            password=os.getenv("DB_PASSWORD"),
        )
        logger.info("Pool de conexiones inicializado correctamente")
    except Exception as e:
        logger.error(f"Error al inicializar pool de conexiones: {e}")
        raise

def get_connection():
    """Obtiene una conexión del pool"""
    global connection_pool
    if connection_pool is None:
        init_connection_pool()
    
    try:
        conn = connection_pool.getconn()
        if conn is None:
            raise Exception("No se pudo obtener conexión del pool")
        return conn
    except Exception as e:
        logger.error(f"Error al obtener conexión: {e}")
        raise

def return_connection(conn):
    """Devuelve una conexión al pool"""
    global connection_pool
    if connection_pool:
        connection_pool.putconn(conn)