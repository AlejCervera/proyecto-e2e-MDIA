-- Esquema de la base de datos.
-- PostgreSQL ejecuta este fichero automáticamente SOLO la primera vez que arranca
-- con el volumen vacío (carpeta /docker-entrypoint-initdb.d).

-- ---------------------------------------------------------------------------
-- Posiciones: una fila por tren y por lectura del feed
-- ---------------------------------------------------------------------------
CREATE TABLE train_positions (
    id                 BIGSERIAL PRIMARY KEY,
    vehicle_id         TEXT NOT NULL,
    trip_id            TEXT,
    route_id           TEXT,              -- el feed actual no lo trae; se deja por si aparece
    stop_id            TEXT,
    status             TEXT,
    latitude           DOUBLE PRECISION NOT NULL CHECK (latitude  BETWEEN -90  AND 90),
    longitude          DOUBLE PRECISION NOT NULL CHECK (longitude BETWEEN -180 AND 180),
    position_timestamp TIMESTAMPTZ,       -- hora de la posición según Renfe (header.timestamp)
    received_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),  -- hora de recepción en el colector
    raw_payload        JSONB              -- entidad original del feed, para auditoría
);

-- Deduplicación: si el feed no se ha actualizado (mismo header.timestamp),
-- la misma posición de un tren no se guarda dos veces.
CREATE UNIQUE INDEX uq_positions_vehicle_ts
    ON train_positions (vehicle_id, position_timestamp);

-- "Posición más reciente de un tren" (GET /getTren/{id} en la fase 5)
CREATE INDEX ix_positions_vehicle_received
    ON train_positions (vehicle_id, received_at DESC);

-- "Posiciones recientes de todos los trenes" (mapa del frontend)
CREATE INDEX ix_positions_received
    ON train_positions (received_at DESC);

-- ---------------------------------------------------------------------------
-- Alertas: una fila por par de trenes bajo el umbral y por lectura
-- ---------------------------------------------------------------------------
CREATE TABLE train_alerts (
    id                 BIGSERIAL PRIMARY KEY,
    train_a            TEXT NOT NULL,
    train_b            TEXT NOT NULL,
    lat_a              DOUBLE PRECISION NOT NULL,
    lon_a              DOUBLE PRECISION NOT NULL,
    lat_b              DOUBLE PRECISION NOT NULL,
    lon_b              DOUBLE PRECISION NOT NULL,
    distance_m         DOUBLE PRECISION NOT NULL CHECK (distance_m >= 0),
    threshold_m        DOUBLE PRECISION NOT NULL CHECK (threshold_m > 0),
    same_stop          BOOLEAN NOT NULL,
    both_stopped       BOOLEAN NOT NULL,
    position_timestamp TIMESTAMPTZ,
    detected_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    -- El par se guarda siempre ordenado (A < B), así A-B y B-A no pueden coexistir
    CHECK (train_a < train_b)
);

-- Deduplicación: una alerta por par y por instantánea del feed
CREATE UNIQUE INDEX uq_alerts_pair_ts
    ON train_alerts (train_a, train_b, position_timestamp);

-- "Alertas más recientes" (GET /getAlertas en la fase 5)
CREATE INDEX ix_alerts_detected
    ON train_alerts (detected_at DESC);
