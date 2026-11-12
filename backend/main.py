"""API REST sobre las posiciones y alertas guardadas por el colector.

Documentación interactiva (Swagger): /docs
"""
import os
from typing import Literal

import psycopg
from fastapi import FastAPI, HTTPException, Path, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from geo import haversine_m
from . import db
from .schemas import Alert, Distance, ErrorMessage, Health, TrainPosition

# Una posición más antigua que esto se considera "no reciente"
MAX_POSITION_AGE_SECONDS = int(os.getenv("MAX_POSITION_AGE_SECONDS", "120"))
CORS_ORIGINS = os.getenv("CORS_ORIGINS", "*").split(",")

app = FastAPI(
    title="RENFE: alertas de proximidad",
    description=(
        "API de consulta de posiciones de trenes y alertas de proximidad.\n\n"
        "⚠️ Datos operativos orientativos, con posible retraso o imprecisión GPS. "
        "**No es un sistema de seguridad ferroviaria.**"
    ),
    version="1.0.0",
)

# Permite que el frontend (otro origen) llame a la API desde el navegador
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_methods=["GET"],
    allow_headers=["*"],
)


@app.exception_handler(psycopg.Error)
async def database_error_handler(request: Request, exc: psycopg.Error):
    """Cualquier error de BD en cualquier endpoint se convierte en un 503 claro."""
    print(f"ERROR de base de datos en {request.url.path}: {exc}")
    return JSONResponse(status_code=503, content={"detail": "Base de datos no disponible"})


# ---------------------------------------------------------------------------
# Consultas SQL
# ---------------------------------------------------------------------------

POSITION_COLUMNS = """
    vehicle_id, trip_id, route_id, stop_id, status, latitude, longitude,
    position_timestamp, received_at,
    EXTRACT(EPOCH FROM (NOW() - received_at))::float AS age_seconds
"""

SQL_LATEST_POSITION = f"""
    SELECT {POSITION_COLUMNS}
    FROM train_positions
    WHERE vehicle_id = %s
    ORDER BY received_at DESC
    LIMIT 1
"""

SQL_RECENT_POSITIONS = f"""
    SELECT DISTINCT ON (vehicle_id) {POSITION_COLUMNS}
    FROM train_positions
    WHERE received_at > NOW() - make_interval(secs => %s)
    ORDER BY vehicle_id, received_at DESC
"""

ALERT_COLUMNS = """
    id, train_a, train_b, lat_a, lon_a, lat_b, lon_b, distance_m, threshold_m,
    same_stop, both_stopped, position_timestamp, detected_at
"""


def get_latest_position(vehicle_id: str) -> dict:
    """Última posición de un tren, o 404 si no existe."""
    row = db.fetch_one(SQL_LATEST_POSITION, (vehicle_id,))
    if row is None:
        raise HTTPException(status_code=404, detail=f"Tren '{vehicle_id}' no encontrado")
    return row


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.get(
    "/getAlertas",
    response_model=list[Alert],
    summary="Alertas registradas",
    tags=["alertas"],
)
def get_alertas(
    limit: int = Query(50, ge=1, le=1000, description="Número máximo de alertas a devolver"),
    order: Literal["desc", "asc"] = Query("desc", description="desc = más recientes primero"),
):
    direction = "DESC" if order == "desc" else "ASC"  # lista blanca: nunca texto libre en el SQL
    sql = f"SELECT {ALERT_COLUMNS} FROM train_alerts ORDER BY detected_at {direction}, id {direction} LIMIT %s"
    return db.fetch_all(sql, (limit,))


@app.get(
    "/getTren/{id}",
    response_model=TrainPosition,
    summary="Datos y posición más reciente de un tren",
    tags=["trenes"],
    responses={404: {"model": ErrorMessage, "description": "El tren no existe"}},
)
def get_tren(id: str = Path(description="Identificador del vehículo (vehicle_id)", examples=["15726"])):
    return get_latest_position(id)


@app.get(
    "/getDistancia/{trenId1}/{trenId2}",
    response_model=Distance,
    summary="Distancia actual en metros entre dos trenes",
    tags=["trenes"],
    responses={
        400: {"model": ErrorMessage, "description": "Se ha pedido el mismo tren dos veces"},
        404: {"model": ErrorMessage, "description": "Alguno de los trenes no existe"},
        409: {"model": ErrorMessage, "description": "Alguna posición no es reciente"},
    },
)
def get_distancia(trenId1: str, trenId2: str):
    if trenId1 == trenId2:
        raise HTTPException(status_code=400, detail="Los dos identificadores son el mismo tren")

    p1 = get_latest_position(trenId1)
    p2 = get_latest_position(trenId2)

    stale = [p["vehicle_id"] for p in (p1, p2) if p["age_seconds"] > MAX_POSITION_AGE_SECONDS]
    if stale:
        raise HTTPException(
            status_code=409,
            detail=f"Posición no reciente (más de {MAX_POSITION_AGE_SECONDS} s) para: {', '.join(stale)}",
        )

    distance = haversine_m(p1["latitude"], p1["longitude"], p2["latitude"], p2["longitude"])
    return {"train_1": p1, "train_2": p2, "distance_m": round(distance, 1)}


@app.get(
    "/getTrenes",
    response_model=list[TrainPosition],
    summary="Posición más reciente de cada tren activo (para el mapa)",
    tags=["trenes"],
)
def get_trenes(
    max_age_seconds: int = Query(
        MAX_POSITION_AGE_SECONDS, ge=1, le=86400,
        description="Solo trenes con posición recibida en los últimos N segundos",
    ),
):
    return db.fetch_all(SQL_RECENT_POSITIONS, (max_age_seconds,))


@app.get("/health", response_model=Health, summary="Estado del servicio", tags=["sistema"])
def health():
    db.fetch_one("SELECT 1")  # si falla, el manejador global devuelve 503
    return {"status": "ok", "database": "ok"}
