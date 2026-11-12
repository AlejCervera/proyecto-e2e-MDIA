"""Persistencia en PostgreSQL de las posiciones y alertas del colector.

La conexión se configura con variables de entorno. Si DB_HOST no está definida,
la persistencia queda desactivada y el colector funciona solo por consola (fase 1).
"""
import os

import psycopg
from psycopg.types.json import Jsonb

DB_HOST = os.getenv("DB_HOST")
DB_PORT = int(os.getenv("DB_PORT", "5432"))
DB_NAME = os.getenv("DB_NAME", "renfe")
DB_USER = os.getenv("DB_USER", "renfe")
DB_PASSWORD = os.getenv("DB_PASSWORD")

INSERT_POSITION = """
    INSERT INTO train_positions
        (vehicle_id, trip_id, stop_id, status, latitude, longitude,
         position_timestamp, received_at, raw_payload)
    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
    ON CONFLICT (vehicle_id, position_timestamp) DO NOTHING
"""

INSERT_ALERT = """
    INSERT INTO train_alerts
        (train_a, train_b, lat_a, lon_a, lat_b, lon_b, distance_m, threshold_m,
         same_stop, both_stopped, position_timestamp, detected_at)
    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    ON CONFLICT (train_a, train_b, position_timestamp) DO NOTHING
"""

_conn = None  # conexión reutilizada entre lecturas


def is_enabled():
    """True si hay base de datos configurada."""
    return bool(DB_HOST)


def _get_connection():
    """Devuelve la conexión abierta, o abre una nueva si no hay o se cerró."""
    global _conn
    if _conn is None or _conn.closed:
        _conn = psycopg.connect(
            host=DB_HOST, port=DB_PORT, dbname=DB_NAME,
            user=DB_USER, password=DB_PASSWORD,
            connect_timeout=5, autocommit=True,
        )
    return _conn


def save_reading(trains, alerts):
    """Guarda posiciones y alertas de una lectura en UNA transacción.

    Devuelve (posiciones_insertadas, alertas_insertadas), o None si falla.
    Si falla, se descarta la conexión y se reintenta en la siguiente lectura.
    """
    global _conn
    positions_rows = [
        (t["vehicle_id"], t["trip_id"], t["stop_id"], t["status"],
         t["latitude"], t["longitude"], t["position_timestamp"], t["received_at"],
         Jsonb(t["raw"]))
        for t in trains
    ]
    alert_rows = [
        (a["train_a"], a["train_b"], a["lat_a"], a["lon_a"], a["lat_b"], a["lon_b"],
         a["distance_m"], a["threshold_m"], a["same_stop"], a["both_stopped"],
         a["position_timestamp"], a["detected_at"])
        for a in alerts
    ]

    try:
        conn = _get_connection()
        with conn.transaction():  # o se guarda todo, o nada
            with conn.cursor() as cur:
                cur.executemany(INSERT_POSITION, positions_rows)
                inserted_positions = max(cur.rowcount, 0)
                cur.executemany(INSERT_ALERT, alert_rows)
                inserted_alerts = max(cur.rowcount, 0)
        return inserted_positions, inserted_alerts
    except psycopg.Error as e:
        print(f"ERROR de base de datos: {e}")
        if _conn is not None:
            _conn.close()
        _conn = None
        return None


def close():
    """Cierra la conexión al terminar el programa."""
    if _conn is not None and not _conn.closed:
        _conn.close()
