"""Modelos Pydantic: definen y validan la forma de las respuestas de la API."""
from datetime import datetime

from pydantic import BaseModel, Field


class TrainPosition(BaseModel):
    vehicle_id: str = Field(examples=["15726"])
    trip_id: str | None = Field(default=None, examples=["1572612026-11-11"])
    route_id: str | None = None
    stop_id: str | None = Field(default=None, examples=["79104"])
    status: str | None = Field(default=None, examples=["IN_TRANSIT_TO"])
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    position_timestamp: datetime | None = Field(description="Hora de la posición según Renfe")
    received_at: datetime = Field(description="Hora de recepción en el colector")
    age_seconds: float = Field(description="Segundos transcurridos desde received_at")


class Alert(BaseModel):
    id: int
    train_a: str
    train_b: str
    lat_a: float
    lon_a: float
    lat_b: float
    lon_b: float
    distance_m: float = Field(ge=0, description="Distancia entre los trenes en metros")
    threshold_m: float = Field(gt=0, description="Umbral configurado en el momento de la alerta")
    same_stop: bool
    both_stopped: bool
    position_timestamp: datetime | None
    detected_at: datetime


class Distance(BaseModel):
    train_1: TrainPosition
    train_2: TrainPosition
    distance_m: float = Field(ge=0, description="Distancia Haversine en metros")


class Health(BaseModel):
    status: str
    database: str


class ErrorMessage(BaseModel):
    detail: str
