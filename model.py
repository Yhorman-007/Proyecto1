from pydantic import BaseModel, Field, field_validator
from datetime import date, datetime
from typing import Optional

class ProductoCreate(BaseModel):
    """Modelo para crear un producto (sin ID)"""
    nombre: str = Field(..., min_length=1, max_length=255, description="Nombre del producto (1-255 caracteres)")
    descripcion: str = Field(default="", max_length=1000, description="Descripción del producto (máx 1000 caracteres)")
    estado: str = Field(..., description="Estado del producto: 'activo' o 'descontinuado'")
    fecha_entrada: date
    nivel_minimo_stock: int = Field(..., gt=0, description="Nivel mínimo de stock debe ser mayor a 0")
    proveedor_id: int
    impuesto_id: int
    
    @field_validator('estado')
    @classmethod
    def validar_estado(cls, v):
        if v.lower() not in ['activo', 'descontinuado']:
            raise ValueError("El estado debe ser 'activo' o 'descontinuado'")
        return v.lower()
    
    # VALIDACIÓN DE FECHAS
    @field_validator('fecha_entrada')
    @classmethod
    def validar_fecha_entrada(cls, v):
        if v > date.today():
            raise ValueError("La fecha de entrada no puede ser futura")
        return v

class Producto(BaseModel):
    """Modelo completo de producto (con ID)"""
    id: int
    nombre: str
    descripcion: str
    estado: str
    fecha_entrada: date
    nivel_minimo_stock: int
    proveedor_id: int
    impuesto_id: int

# Modelos para autenticación JWT
class UsuarioBase(BaseModel):
    """Modelo base de usuario"""
    username: str
    email: str

class UsuarioCreate(UsuarioBase):
    """Modelo para crear un usuario"""
    password: str = Field(..., min_length=6, description="Contraseña (mínimo 6 caracteres)")

class Usuario(UsuarioBase):
    """Modelo completo de usuario (con ID y datos de BD)"""
    id: int
    hashed_password: str
    is_active: bool = True

class UsuarioResponse(UsuarioBase):
    """Modelo de respuesta de usuario (sin contraseña)"""
    id: int
    is_active: bool

class Token(BaseModel):
    """Modelo de respuesta de token"""
    access_token: str
    token_type: str = "bearer"

class TokenData(BaseModel):
    """Datos del token"""
    username: Optional[str] = None