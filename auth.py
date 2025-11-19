import os
from datetime import datetime, timedelta
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from passlib.context import CryptContext
from jose import JWTError, jwt

from db import get_connection, return_connection
from model import Usuario
from dotenv import load_dotenv

load_dotenv()

# ============================
# CONFIGURACIÓN
# ============================

SECRET_KEY = os.getenv("JWT_SECRET_KEY", "super-secret-key-cambiar")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30"))

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Extrae correctamente el token de Authorization: Bearer <token>
oauth2_scheme = HTTPBearer()


# ============================
# UTILIDADES DE CONTRASEÑA
# ============================

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)


# ============================
# TOKEN: CREACIÓN Y VALIDACIÓN
# ============================

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()

    expire = datetime.utcnow() + (
        expires_delta if expires_delta else timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    )

    to_encode.update({"exp": expire})

    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def verify_token(token: str) -> dict:
    """
    Decodifica y valida un JWT.
    """
    try:
        payload = jwt.decode(
            token,
            SECRET_KEY,
            algorithms=[ALGORITHM]
        )
        return payload

    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido o expirado",
            headers={"WWW-Authenticate": "Bearer"},
        )


# ============================
# CONSULTAS A BD
# ============================

def get_user_by_username(username: str) -> Optional[Usuario]:
    conn = None
    cur = None

    try:
        conn = get_connection()
        cur = conn.cursor()

        cur.execute(
            "SELECT id, username, email, hashed_password, is_active FROM usuarios WHERE username = %s",
            (username,),
        )
        row = cur.fetchone()

        if row:
            return Usuario(
                id=row[0],
                username=row[1],
                email=row[2],
                hashed_password=row[3],
                is_active=row[4],
            )

        return None

    finally:
        if cur:
            cur.close()
        if conn:
            return_connection(conn)


def authenticate_user(username: str, password: str) -> Optional[Usuario]:
    user = get_user_by_username(username)

    if not user:
        return None
    if not verify_password(password, user.hashed_password):
        return None
    if not user.is_active:
        return None

    return user


# ============================
# DEPENDENCIAS FASTAPI
# ============================

async def get_current_user(
    token_data: HTTPAuthorizationCredentials = Depends(oauth2_scheme)
) -> Usuario:

    # Extrae SOLO el token string
    token = token_data.credentials

    # Decodifica el JWT
    payload = verify_token(token)

    username: str = payload.get("sub")

    if username is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido: no contiene 'sub'"
        )

    user = get_user_by_username(username)

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuario no encontrado"
        )

    return user


async def get_current_active_user(
    current_user: Usuario = Depends(get_current_user)
) -> Usuario:

    if not current_user.is_active:
        raise HTTPException(
            status_code=400,
            detail="Usuario inactivo"
        )

    return current_user
