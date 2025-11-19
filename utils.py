"""
Utilidades y helpers para el CRUD
POC: Helper para mapeo de filas a diccionarios
"""
from typing import List, Dict, Any
import logging

logger = logging.getLogger(__name__)

# HELPER PARA MAPEO DE FILAS
def row_to_dict(cursor, row) -> Dict[str, Any]:
    """
    Convierte una fila de la BD a un diccionario usando nombres de columnas.
    
    Args:
        cursor: Cursor de psycopg2 con la query ejecutada
        row: Tupla con los valores de la fila
    
    Returns:
        Diccionario con los valores mapeados por nombre de columna
    """
    if row is None:
        return None
    
    column_names = [desc[0] for desc in cursor.description]
    return dict(zip(column_names, row))

def rows_to_dict_list(cursor, rows: List[tuple]) -> List[Dict[str, Any]]:
    """
    Convierte múltiples filas a una lista de diccionarios.
    
    Args:
        cursor: Cursor de psycopg2 con la query ejecutada
        rows: Lista de tuplas con los valores
    
    Returns:
        Lista de diccionarios
    """
    return [row_to_dict(cursor, row) for row in rows] if rows else []

