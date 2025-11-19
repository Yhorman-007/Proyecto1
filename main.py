from fastapi import FastAPI, HTTPException, Query, Depends, status
from db import get_connection, return_connection, init_connection_pool
from model import Producto, ProductoCreate, UsuarioCreate, UsuarioResponse, Token, Usuario
from utils import row_to_dict, rows_to_dict_list
from auth import (
    authenticate_user, create_access_token, get_current_active_user,
    get_password_hash, get_user_by_username, ACCESS_TOKEN_EXPIRE_MINUTES
)
from datetime import timedelta
import psycopg2
import logging
from typing import Optional
from fastapi.security import HTTPBearer

from pydantic import BaseModel

class LoginRequest(BaseModel):
    username: str
    password: str


# LOGGING
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="CRUD de Productos con FastAPI + PostgreSQL",
    description="API REST con autenticación JWT para gestión de productos"
)

@app.get("/")
def read_root():
    """
    Ruta raíz para verificar que la API está funcionando.
    """
    logger.info("Acceso a la ruta raíz (/), retornando estado OK.")
    return {
        "title": app.title,
        "description": app.description,
        "status": "online",
        "documentation": "/docs"
    }


# Inicializar pool de conexiones al iniciar la app
@app.on_event("startup")
async def startup_event():
    """Inicializa el pool de conexiones al arrancar la aplicación"""
    try:
        init_connection_pool()
        logger.info("Aplicación iniciada correctamente")
    except Exception as e:
        logger.error(f"Error al iniciar aplicación: {e}")
        raise

@app.on_event("shutdown")
async def shutdown_event():
    """Cierra el pool de conexiones al detener la aplicación"""
    logger.info("Aplicación detenida")

# MEJOR MANEJO DE EXCEPCIONES
def handle_db_exception(e: Exception, operation: str):
    """Maneja excepciones de base de datos de forma específica"""
    if isinstance(e, psycopg2.IntegrityError):
        
        # UNICIDAD DE NOMBRE
        if "unique" in str(e).lower() or "duplicate" in str(e).lower():
            logger.warning(f"Intento de crear producto duplicado: {operation}")
            raise HTTPException(
                status_code=409,
                detail="Ya existe un producto con ese nombre"
            )
        logger.error(f"Error de integridad en {operation}: {e}")
        raise HTTPException(status_code=400, detail=f"Error de integridad: {str(e)}")
    
    elif isinstance(e, psycopg2.OperationalError):
        logger.error(f"Error de conexión en {operation}: {e}")
        raise HTTPException(
            status_code=503,
            detail="Error de conexión con la base de datos. Intente más tarde."
        )
    else:
        logger.error(f"Error desconocido en {operation}: {e}")
        raise HTTPException(status_code=500, detail=f"Error interno: {str(e)}")

# VALIDACIÓN DE RELACIONES
def validar_proveedor(conn, proveedor_id: int):
    """
    Valida que el proveedor exista.
    Nota: Si la tabla 'proveedores' no existe, la validación se omite.
    """
    cur = conn.cursor()
    try:
        # Verificar si la tabla existe
        cur.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_name = 'proveedores'
            )
        """)
        tabla_existe = cur.fetchone()[0]
        
        if tabla_existe:
            cur.execute("SELECT id FROM proveedores WHERE id = %s", (proveedor_id,))
            if not cur.fetchone():
                raise HTTPException(
                    status_code=404,
                    detail=f"Proveedor con ID {proveedor_id} no existe"
                )
    finally:
        cur.close()

def validar_impuesto(conn, impuesto_id: int):
    """
    Valida que el impuesto exista.
    Nota: Si la tabla 'impuestos' no existe, la validación se omite.
    """
    cur = conn.cursor()
    try:
        # Verificar si la tabla existe
        cur.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_name = 'impuestos'
            )
        """)
        tabla_existe = cur.fetchone()[0]
        
        if tabla_existe:
            cur.execute("SELECT id FROM impuestos WHERE id = %s", (impuesto_id,))
            if not cur.fetchone():
                raise HTTPException(
                    status_code=404,
                    detail=f"Impuesto con ID {impuesto_id} no existe"
                )
    finally:
        cur.close()

# ============================================
# 🔐 ENDPOINTS DE AUTENTICACIÓN
# ============================================

@app.post("/register", response_model=UsuarioResponse, status_code=status.HTTP_201_CREATED)
def register(usuario: UsuarioCreate):
    """
    Registra un nuevo usuario en el sistema.
    
    POC: AUTENTICACIÓN JWT
    ¿Qué es?: Sistema de autenticación usando JSON Web Tokens.
    Beneficio: Permite identificar usuarios y proteger endpoints.
    En producción: Esencial para APIs que requieren seguridad.
    """
    conn = None
    cur = None
    try:
        logger.info(f"Registrando usuario: {usuario.username}")
        conn = get_connection()
        cur = conn.cursor()
        
        # Verificar si el usuario ya existe
        cur.execute("SELECT id FROM usuarios WHERE username = %s OR email = %s", 
                   (usuario.username, usuario.email))
        if cur.fetchone():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="El usuario o email ya está registrado"
            )
        
        # Hashear la contraseña
        hashed_password = get_password_hash(usuario.password)
        
        # Insertar usuario
        cur.execute("""
            INSERT INTO usuarios (username, email, hashed_password, is_active)
            VALUES (%s, %s, %s, %s)
            RETURNING id;
        """, (usuario.username, usuario.email, hashed_password, True))
        
        user_id = cur.fetchone()[0]
        conn.commit()
        logger.info(f"Usuario {usuario.username} registrado exitosamente")
        
        return UsuarioResponse(
            id=user_id,
            username=usuario.username,
            email=usuario.email,
            is_active=True
        )
    except HTTPException:
        if conn:
            conn.rollback()
        raise
    except Exception as e:
        if conn:
            conn.rollback()
        handle_db_exception(e, "register")
    finally:
        if cur:
            cur.close()
        if conn:
            return_connection(conn)

@app.post("/login", response_model=Token)
def login(data: LoginRequest):
    """
    Autentica un usuario y retorna un token JWT.

    Este endpoint recibe JSON:
    {
        "username": "usuario",
        "password": "clave"
    }
    """
    logger.info(f"Intento de login para usuario: {data.username}")
    
    user = authenticate_user(data.username, data.password)
    if not user:
        logger.warning(f"Login fallido para usuario: {data.username}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuario o contraseña incorrectos",
        )
    
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.username},
        expires_delta=access_token_expires
    )
    
    logger.info(f"Login exitoso para usuario: {data.username}")
    return {"access_token": access_token, "token_type": "bearer"}

@app.get("/me", response_model=UsuarioResponse)
def get_current_user_info(current_user: Usuario = Depends(get_current_active_user)):
    """
    Obtiene la información del usuario actual autenticado.
    
    Requiere autenticación JWT.
    """
    return UsuarioResponse(
        id=current_user.id,
        username=current_user.username,
        email=current_user.email,
        is_active=current_user.is_active
    )

# ============================================
# 📦 ENDPOINTS DEL CRUD (PROTEGIDOS CON JWT)
# ============================================

# 🟢 Crear un producto
@app.post("/productos/", response_model=Producto)
def crear_producto(
    producto: ProductoCreate,
    current_user: Usuario = Depends(get_current_active_user)
):
    """
    Crea un nuevo producto.
    
    Valida:
    - Que el nombre sea único
    - Que el proveedor exista
    - Que el impuesto exista
    - Que la fecha no sea futura
    """
    conn = None
    cur = None
    try:
        logger.info(f"Creando producto: {producto.nombre}")
        conn = get_connection()
        cur = conn.cursor()
        
        # Validar relaciones
        validar_proveedor(conn, producto.proveedor_id)
        validar_impuesto(conn, producto.impuesto_id)
        
        # Validar unicidad de nombre
        cur.execute("SELECT id FROM productos WHERE nombre = %s", (producto.nombre,))
        if cur.fetchone():
            raise HTTPException(
                status_code=409,
                detail="Ya existe un producto con ese nombre"
            )
        
        cur.execute("""
            INSERT INTO productos (nombre, descripcion, estado, fecha_entrada, nivel_minimo_stock, proveedor_id, impuesto_id)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            RETURNING id;
        """, (
            producto.nombre, producto.descripcion, producto.estado,
            producto.fecha_entrada, producto.nivel_minimo_stock, producto.proveedor_id, producto.impuesto_id
        ))
        
        producto_id = cur.fetchone()[0]
        conn.commit()
        logger.info(f"Producto creado exitosamente con ID: {producto_id}")
        
        return Producto(
            id=producto_id,
            nombre=producto.nombre,
            descripcion=producto.descripcion,
            estado=producto.estado,
            fecha_entrada=producto.fecha_entrada,
            nivel_minimo_stock=producto.nivel_minimo_stock,
            proveedor_id=producto.proveedor_id,
            impuesto_id=producto.impuesto_id
        )
    except HTTPException:
        if conn:
            conn.rollback()
        raise
    except Exception as e:
        if conn:
            conn.rollback()
        handle_db_exception(e, "crear_producto")
    finally:
        if cur:
            cur.close()
        if conn:
            return_connection(conn)


# 🔵 Obtener todos los productos
# PAGINACIÓN
# FILTROS Y BÚSQUEDA

@app.get("/productos/", response_model=list[Producto])
def obtener_productos(
    current_user: Usuario = Depends(get_current_active_user),
    skip: int = Query(0, ge=0, description="Número de registros a saltar (paginación)"),
    limit: int = Query(10, ge=1, le=100, description="Número máximo de registros a retornar (1-100)"),
    estado: Optional[str] = Query(None, description="Filtrar por estado: 'activo' o 'descontinuado'"),
    proveedor_id: Optional[int] = Query(None, description="Filtrar por ID de proveedor"),
    search: Optional[str] = Query(None, description="Buscar en nombre y descripción")
):
    """
    Obtiene una lista de productos con paginación, filtros y búsqueda.
    
    Parámetros:
    - skip: Registros a saltar (para paginación)
    - limit: Máximo de registros a retornar (1-100)
    - estado: Filtrar por estado
    - proveedor_id: Filtrar por proveedor
    - search: Buscar texto en nombre y descripción
    """
    conn = None
    cur = None
    try:
        logger.info(f"Obteniendo productos - skip: {skip}, limit: {limit}, estado: {estado}, search: {search}")
        conn = get_connection()
        cur = conn.cursor()
        
        # Construir query dinámicamente
        query = "SELECT * FROM productos WHERE 1=1"
        params = []
        
        if estado:
            query += " AND estado = %s"
            params.append(estado.lower())
        
        if proveedor_id:
            query += " AND proveedor_id = %s"
            params.append(proveedor_id)
        
        if search:
            query += " AND (nombre ILIKE %s OR descripcion ILIKE %s)"
            search_pattern = f"%{search}%"
            params.extend([search_pattern, search_pattern])
        
        query += " ORDER BY id LIMIT %s OFFSET %s"
        params.extend([limit, skip])
        
        cur.execute(query, params)
        rows = cur.fetchall()
        
        productos = rows_to_dict_list(cur, rows)
        logger.info(f"Retornados {len(productos)} productos")
        
        return [Producto(**p) for p in productos]
    except Exception as e:
        handle_db_exception(e, "obtener_productos")
    finally:
        if cur:
            cur.close()
        if conn:
            return_connection(conn)


# 🟡 Obtener un producto por ID
@app.get("/productos/{producto_id}", response_model=Producto)
def obtener_producto(
    producto_id: int,
    current_user: Usuario = Depends(get_current_active_user)
):
    """Obtiene un producto específico por su ID"""
    conn = None
    cur = None
    try:
        logger.info(f"Obteniendo producto con ID: {producto_id}")
        conn = get_connection()
        cur = conn.cursor()
        
        cur.execute("SELECT * FROM productos WHERE id = %s", (producto_id,))
        row = cur.fetchone()
        
        if row:
            producto_dict = row_to_dict(cur, row)
            logger.info(f"Producto encontrado: {producto_dict['nombre']}")
            return Producto(**producto_dict)
        else:
            logger.warning(f"Producto con ID {producto_id} no encontrado")
            raise HTTPException(status_code=404, detail="Producto no encontrado")
    except HTTPException:
        raise
    except Exception as e:
        handle_db_exception(e, "obtener_producto")
    finally:
        if cur:
            cur.close()
        if conn:
            return_connection(conn)


# 🟠 Actualizar un producto
@app.put("/productos/{producto_id}", response_model=Producto)
def actualizar_producto(
    producto_id: int,
    producto: ProductoCreate,
    current_user: Usuario = Depends(get_current_active_user)
):
    """
    Actualiza un producto existente.
    
    Valida:
    - Que el producto exista
    - Que el nombre sea único (si cambió)
    - Que el proveedor exista
    - Que el impuesto exista
    """
    conn = None
    cur = None
    try:
        logger.info(f"Actualizando producto con ID: {producto_id}")
        conn = get_connection()
        cur = conn.cursor()
        
        # Verificar que el producto existe
        cur.execute("SELECT nombre FROM productos WHERE id = %s", (producto_id,))
        producto_existente = cur.fetchone()
        if not producto_existente:
            raise HTTPException(status_code=404, detail="Producto no encontrado")
        
        # Validar relaciones
        validar_proveedor(conn, producto.proveedor_id)
        validar_impuesto(conn, producto.impuesto_id)
        
        # Validar unicidad de nombre (solo si cambió)
        nombre_anterior = producto_existente[0]
        if producto.nombre != nombre_anterior:
            cur.execute("SELECT id FROM productos WHERE nombre = %s AND id != %s", 
                       (producto.nombre, producto_id))
            if cur.fetchone():
                raise HTTPException(
                    status_code=409,
                    detail="Ya existe otro producto con ese nombre"
                )
        
        cur.execute("""
            UPDATE productos
            SET nombre=%s, descripcion=%s, estado=%s, fecha_entrada=%s,
                nivel_minimo_stock=%s, proveedor_id=%s, impuesto_id=%s
            WHERE id=%s
        """, (
            producto.nombre, producto.descripcion, producto.estado,
            producto.fecha_entrada, producto.nivel_minimo_stock,
            producto.proveedor_id, producto.impuesto_id, producto_id
        ))
        
        conn.commit()
        if cur.rowcount == 0:
            raise HTTPException(status_code=404, detail="Producto no encontrado")
        
        logger.info(f"Producto {producto_id} actualizado exitosamente")
        
        return Producto(
            id=producto_id,
            nombre=producto.nombre,
            descripcion=producto.descripcion,
            estado=producto.estado,
            fecha_entrada=producto.fecha_entrada,
            nivel_minimo_stock=producto.nivel_minimo_stock,
            proveedor_id=producto.proveedor_id,
            impuesto_id=producto.impuesto_id
        )
    except HTTPException:
        if conn:
            conn.rollback()
        raise
    except Exception as e:
        if conn:
            conn.rollback()
        handle_db_exception(e, "actualizar_producto")
    finally:
        if cur:
            cur.close()
        if conn:
            return_connection(conn)


# 🔴 Eliminar un producto
@app.delete("/productos/{producto_id}")
def eliminar_producto(
    producto_id: int,
    current_user: Usuario = Depends(get_current_active_user)
):
    """
    Elimina un producto.
    
    REGLA DE NEGOCIO 4: POLÍTICA DE ELIMINACIÓN
    ¿Qué es?: Define cuándo y cómo se pueden eliminar productos.
    Razón: Puede haber restricciones de negocio (ej: no eliminar productos activos).
    Beneficio: Previene eliminaciones accidentales o no permitidas.
    
    Nota: Actualmente permite eliminar cualquier producto.
    En producción, podrías agregar validaciones como:
    - No eliminar productos activos
    - Soft delete en lugar de hard delete
    """
    conn = None
    cur = None
    try:
        logger.info(f"Eliminando producto con ID: {producto_id}")
        conn = get_connection()
        cur = conn.cursor()
        
        cur.execute("DELETE FROM productos WHERE id = %s", (producto_id,))
        conn.commit()
        
        if cur.rowcount == 0:
            logger.warning(f"Intento de eliminar producto inexistente: {producto_id}")
            raise HTTPException(status_code=404, detail="Producto no encontrado")
        
        logger.info(f"Producto {producto_id} eliminado exitosamente")
        return {"mensaje": "Producto eliminado correctamente"}
    except HTTPException:
        if conn:
            conn.rollback()
        raise
    except Exception as e:
        if conn:
            conn.rollback()
        handle_db_exception(e, "eliminar_producto")
    finally:
        if cur:
            cur.close()
        if conn:
            return_connection(conn)
