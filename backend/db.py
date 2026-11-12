"""Acceso a PostgreSQL para el backend (solo lectura)."""
import os

import psycopg
from psycopg.rows import dict_row

DB_CONFIG = {
    "host": os.getenv("DB_HOST", "localhost"),
    "port": int(os.getenv("DB_PORT", "5432")),
    "dbname": os.getenv("DB_NAME", "renfe"),
    "user": os.getenv("DB_USER", "renfe"),
    "password": os.getenv("DB_PASSWORD"),
    "connect_timeout": 5,
}


def fetch_all(sql, params=()):
    """Ejecuta una consulta y devuelve todas las filas como lista de dicts."""
    with psycopg.connect(**DB_CONFIG, row_factory=dict_row) as conn:
        return conn.execute(sql, params).fetchall()


def fetch_one(sql, params=()):
    """Ejecuta una consulta y devuelve la primera fila como dict, o None si no hay."""
    with psycopg.connect(**DB_CONFIG, row_factory=dict_row) as conn:
        return conn.execute(sql, params).fetchone()
