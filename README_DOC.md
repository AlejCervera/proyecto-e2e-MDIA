# RENFE: alerta de proximidad entre trenes (documentación del proyecto)

> El enunciado del ejercicio está en [README.md](README.md). Este documento describe **lo implementado**, cómo ejecutarlo y las decisiones tomadas.

> ⚠️ **Aviso.** Las posiciones del feed son datos operativos orientativos y pueden tener retraso o imprecisión GPS. Las alertas de este proyecto son un ejercicio académico de análisis de datos. **No son un sistema de seguridad ferroviaria.**

## Estado

| Fase | Descripción | Estado |
|---|---|---|
| 1 | Consumo de API y alertas en Python | ✅ Completada |
| 2 | Dockerizar el colector | ✅ Completada |
| 3 | Almacenamiento SQL con Docker Compose | ✅ Completada |
| 4 | Ejecución automática con `docker compose up` | ✅ Completada |
| 5 | Backend FastAPI | ⏳ Pendiente |
| 6 | Frontend | ⏳ Pendiente |

## Estructura del repositorio

```
proyecto-e2e-MDIA/
├── renfe_collector.py        # Colector: descarga, parseo, validación, distancias y alertas
├── storage.py                # Persistencia en PostgreSQL (posiciones y alertas)
├── make_sample.py            # Genera la muestra anonimizada a partir de una captura real
├── db/
│   └── init.sql              # Esquema SQL: tablas e índices
├── samples/
│   └── vehicle_positions_sample.json   # Respuesta real anonimizada (para trabajar sin conexión)
├── Dockerfile                # Imagen del colector
├── docker-compose.yml        # Servicios: db (PostgreSQL) + collector
├── .dockerignore             # Ficheros que no entran en la imagen
├── requirements.txt          # Dependencias Python (versiones fijadas)
├── .env.example              # Plantilla de variables de entorno
├── README.md                 # Enunciado del ejercicio
└── README_DOC.md             # Este documento
```

No se suben al repositorio (`.gitignore`): `.env`, `.venv/`, `data/` (capturas reales sin anonimizar), `__pycache__/` y `.vscode/`.

---

## Inicio rápido (Docker)

Requisito: Docker Desktop (o Docker Engine + Compose) en ejecución.

```powershell
copy .env.example .env      # y cambia POSTGRES_PASSWORD
docker compose up --build
```

Esto levanta PostgreSQL, crea el esquema, espera a que la base de datos esté lista y arranca el colector, que empieza a guardar posiciones y alertas cada 15 s. Los detalles están en [Fases 2-4](#fases-2-4-docker-y-postgresql).

---

## Fase 1: colector en Python

### Requisitos

- Python 3.10 o superior
- Conexión a internet (o la muestra local, ver [Modo sin conexión](#modo-sin-conexión))

### Instalación

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1          # Windows (PowerShell)
# source .venv/bin/activate         # Linux / macOS
pip install -r requirements.txt
```

Dependencias externas: `requests` (HTTP) y `psycopg[binary]` (PostgreSQL). El resto de módulos son de la librería estándar.

Sin `DB_HOST` definida, el colector funciona **solo por consola** (comportamiento de la Fase 1). Con ella, además guarda en la base de datos.

### Configuración

Variables de entorno (ver [.env.example](.env.example)):

| Variable | Por defecto | Descripción |
|---|---|---|
| `ALERT_DISTANCE_METERS` | `1000` | Umbral en metros. Se genera alerta si dos trenes están a una distancia **estrictamente menor**. |
| `POLL_INTERVAL_SECONDS` | `15` | Segundos entre lecturas. **Mínimo 15**: si se indica un valor menor, se fuerza a 15 porque la fuente se actualiza cada ~15 s. |
| `FEED_FILE` | *(vacía)* | Si se define, se lee este fichero JSON en lugar de llamar a la API. |

> El colector lee las variables del entorno del sistema; **no lee el fichero `.env` por sí mismo**. El `.env` lo usará Docker Compose en fases posteriores. En local se definen en la terminal (ver ejemplos abajo).

### Ejecución

**Contra la API real**, con los valores por defecto:

```powershell
python renfe_collector.py
```

**Con otro umbral** (PowerShell):

```powershell
$env:ALERT_DISTANCE_METERS = "5000"
python renfe_collector.py
```

**Modo sin conexión**, con la muestra anonimizada:

```powershell
$env:FEED_FILE = "samples/vehicle_positions_sample.json"
python renfe_collector.py
```

Para volver a la API: `Remove-Item Env:FEED_FILE`.

El colector se ejecuta en bucle hasta que se pulsa `Ctrl+C`.

### Ejemplo de salida

Con la muestra anonimizada y el umbral por defecto (1000 m):

```
Colector iniciado: umbral 1000.0 m, cada 15 s
Pulsa Ctrl+C para detener.

[2026-11-12 17:40:55 UTC] 155 trenes, 7 alertas
  tren T001: (40.033897, -2.143631) STOPPED_AT → parada 03208
  tren T002: (38.902493, -1.7388251) IN_TRANSIT_TO → parada 60911
  tren T003: (37.321777, -5.337344) STOPPED_AT → parada 01007
  tren T004: (37.268776, -5.896837) IN_TRANSIT_TO → parada 51103
  tren T005: (40.060913, -2.2147002) STOPPED_AT → parada 17000
  ... y 150 más
  ALERTA: T010 ↔ T011 a 0.0 m (umbral 1000.0 m)
  ALERTA: T012 ↔ T063 a 0.0 m (umbral 1000.0 m)
  ALERTA: T094 ↔ T108 a 67.8 m (umbral 1000.0 m)
  ...
```

### Ejemplo de alerta (estructura interna)

Cada alerta es un diccionario con los datos que pide el enunciado:

```python
{
    "train_a": "00280",
    "lat_a": 42.690903,
    "lon_a": -2.9411867,
    "train_b": "00437",
    "lat_b": 42.690685,
    "lon_b": -2.941961,
    "distance_m": 67.8,
    "threshold_m": 1000.0,
    "position_timestamp": datetime(2026, 11, 12, 14, 36, 50, tzinfo=timezone.utc),
    "detected_at": datetime(2026, 11, 12, 17, 16, 29, tzinfo=timezone.utc),
    "same_stop": False,
    "both_stopped": True,
}
```

### Flujo de una lectura

```
load_feed()        API (fetch_feed) o fichero local (FEED_FILE)
     │
parse_feed()       recorre las entidades, deduplica por vehicle_id, añade fechas
     │  └─ parse_entity()   valida y aplana una entidad (o la descarta)
     │
find_alerts()      compara cada par de trenes una vez (Haversine)
     │
run_once()         imprime posiciones y alertas
```

| Función | Responsabilidad |
|---|---|
| `haversine_m(lat1, lon1, lat2, lon2)` | Distancia en metros sobre una esfera de radio 6 371 000 m. Recibe grados. |
| `fetch_feed(url)` | GET con `timeout=10`, `raise_for_status()` y captura de `RequestException`. Devuelve `dict` o `None`. |
| `load_feed()` | Elige la fuente: `FEED_FILE` si está definido, la API si no. Mismo contrato: `dict` o `None`. |
| `parse_entity(entity)` | Extrae y valida los campos de una entidad. Devuelve `dict` o `None`. |
| `parse_feed(feed, received_at)` | Lista de trenes únicos con `position_timestamp` y `received_at`. |
| `find_alerts(trains, threshold_m)` | Lista de alertas para pares con distancia `< threshold_m`. |
| `run_once(threshold_m)` | Una lectura completa: obtener, parsear, alertar e imprimir. |

---

## Fases 2-4: Docker y PostgreSQL

### Arquitectura

```
┌──────────────────────── docker compose ────────────────────────┐
│                                                                │
│   collector (imagen propia)   ──SQL──►   db (postgres:17)      │
│   renfe_collector.py                     tablas train_positions│
│   + storage.py                           y train_alerts        │
│        │                                      │                │
│        │ HTTPS                                ▼                │
│        ▼                                volumen pgdata         │
│   API Renfe                             (persistencia)         │
└────────────────────────────────────────────────────────────────┘
```

### Imagen del colector (Fase 2)

El [Dockerfile](Dockerfile) parte de `python:3.13-slim`, instala `requirements.txt` y copia el código. Decisiones:

- **Dependencias antes que el código**: la capa de `pip install` se cachea y solo se rehace si cambia `requirements.txt`.
- **`PYTHONUNBUFFERED=1`**: los `print()` aparecen al instante en los logs.
- **Usuario sin privilegios** (`appuser`) en lugar de `root`.
- **`.dockerignore`** excluye `.venv/`, `.git/`, `data/` y `.env`: los secretos no entran en la imagen.
- **Parada limpia**: el colector trata `SIGTERM` (lo que envía `docker stop`) igual que `Ctrl+C`, y se detiene al instante en lugar de esperar los 10 s del *timeout* de Docker.

Construir y ejecutar solo el colector, sin base de datos:

```powershell
docker build -t renfe-collector .
docker run --rm -it renfe-collector
docker run --rm -it -e ALERT_DISTANCE_METERS=5000 renfe-collector
docker run --rm -it -e FEED_FILE=samples/vehicle_positions_sample.json renfe-collector
```

### Compose y ejecución automática (Fases 3-4)

[docker-compose.yml](docker-compose.yml) define dos servicios y un volumen:

| Servicio | Qué hace |
|---|---|
| `db` | PostgreSQL 17. En el primer arranque ejecuta [db/init.sql](db/init.sql). Tiene un *healthcheck* con `pg_isready`. |
| `collector` | Se construye con el `Dockerfile`. `depends_on: condition: service_healthy` hace que **no arranque hasta que la BD acepte conexiones**. |
| volumen `pgdata` | Guarda los datos de PostgreSQL. Sobreviven a `docker compose down`. |

Ambos servicios tienen `restart: unless-stopped`.

Variables de entorno adicionales (en `.env`):

| Variable | Uso |
|---|---|
| `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD` | Credenciales de la BD. Compose las pasa a `db` y, como `DB_NAME`, `DB_USER` y `DB_PASSWORD`, al colector. |
| `DB_HOST`, `DB_PORT` | Las fija Compose (`db`, `5432`). `db` es el nombre del servicio, que hace de nombre de host dentro de la red de Compose. |

### Comandos útiles

```powershell
docker compose up --build -d                  # levantar en segundo plano
docker compose logs -f collector              # ver los logs del colector en directo
docker compose ps                             # estado de los servicios
docker compose down                           # parar (los datos se conservan)
docker compose down -v                        # parar Y BORRAR los datos (vuelve a ejecutar init.sql)
```

Cambiar el umbral: edita `ALERT_DISTANCE_METERS` en `.env` y ejecuta `docker compose up -d` (Compose recrea el colector con el nuevo valor).

Consultar la base de datos:

```powershell
docker compose exec db psql -U renfe -d renfe
```

```sql
-- Últimas alertas
SELECT train_a, train_b, distance_m, threshold_m, both_stopped, detected_at
FROM train_alerts ORDER BY detected_at DESC LIMIT 10;

-- Posición más reciente de cada tren
SELECT DISTINCT ON (vehicle_id) vehicle_id, latitude, longitude, status, received_at
FROM train_positions ORDER BY vehicle_id, received_at DESC;
```

### Esquema SQL

Definido en [db/init.sql](db/init.sql).

**`train_positions`**: una fila por tren y por instantánea del feed. Es la tabla propuesta en el enunciado, con `stop_id` y `status` añadidos. `route_id` se mantiene, pero queda vacía porque el feed no la trae. `raw_payload` (JSONB) guarda la entidad original para auditoría.

**`train_alerts`**: una fila por par de trenes bajo el umbral y por instantánea, con ambos ids, sus coordenadas, la distancia, el umbral aplicado, las etiquetas `same_stop` y `both_stopped`, y las dos marcas de tiempo.

**Índices:**

| Índice | Para qué |
|---|---|
| `train_positions (vehicle_id, received_at DESC)` | Posición más reciente de un tren (`/getTren/{id}`) |
| `train_positions (received_at DESC)` | Posiciones recientes de todos los trenes (mapa) |
| `train_alerts (detected_at DESC)` | Alertas más recientes (`/getAlertas`) |
| Únicos: ver deduplicación | |

**Tipos de fecha/hora:** todas las columnas temporales son `TIMESTAMPTZ`. PostgreSQL las almacena en UTC y el colector siempre envía fechas con zona horaria (UTC), así que no hay ambigüedad con horarios de verano ni con la zona del servidor.

### Deduplicación en la base de datos

| Tabla | Clave única | Efecto |
|---|---|---|
| `train_positions` | `(vehicle_id, position_timestamp)` | Si el feed no se ha actualizado entre dos lecturas (mismo `header.timestamp`), las posiciones no se duplican. |
| `train_alerts` | `(train_a, train_b, position_timestamp)` | Un par genera como máximo una alerta por instantánea del feed. |

- Las inserciones usan `ON CONFLICT ... DO NOTHING`: los duplicados se ignoran sin error.
- **Orden canónico del par:** `find_alerts` guarda siempre `train_a < train_b`, y la tabla lo exige con un `CHECK`. Así A-B y B-A no pueden coexistir.
- **Alertas repetidas:** si un par sigue dentro del umbral en lecturas sucesivas, se guarda una alerta por cada instantánea nueva. Esto conserva la evolución de la distancia (por ejemplo, dos trenes acercándose). Agruparlas en "episodios" queda como mejora futura.
- Posiciones y alertas de una lectura se guardan en **una sola transacción**: o se guarda todo, o nada.
- Si la base de datos falla, se registra el error, se descarta la conexión y se reintenta en la siguiente lectura. El colector no se detiene.

Verificado: procesar dos veces la misma muestra inserta 155 posiciones y 7 alertas la primera vez, y 0 y 0 la segunda.

---

## El feed de origen

- Fuente: [Posición vehículos AV, LD y MD (Renfe Data)](https://data.renfe.com/dataset/posicion-vehiculos-av-ld-md)
- Recurso usado: `https://gtfsrt.renfe.com/vehicle_positions_LD.json`
- Formato: **GTFS Realtime 2.0** serializado en JSON. No requiere cabeceras ni autenticación.

Estructura de una entidad:

```json
{
  "id": "VP_15726",
  "vehicle": {
    "trip":     { "tripId": "1572612026-11-11" },
    "position": { "latitude": 41.449234, "longitude": 2.1971467 },
    "currentStatus": "IN_TRANSIT_TO",
    "stopId": "79104",
    "vehicle":  { "id": "15726", "label": "15726" }
  }
}
```

### Mapeo de campos

| Campo pedido en el enunciado | Campo del feed | Campo en el colector | Notas |
|---|---|---|---|
| Identificador del vehículo | `vehicle.vehicle.id` | `vehicle_id` | Obligatorio |
| Latitud / longitud | `vehicle.position.latitude/longitude` | `latitude`, `longitude` | Obligatorios y validados |
| Ruta, línea o servicio | **No existe** (no hay `routeId`) | — | Ver limitaciones |
| Identificador del viaje | `vehicle.trip.tripId` | `trip_id` | Opcional |
| Fecha/hora de la posición | `header.timestamp` (Unix epoch en segundos, **como texto**) | `position_timestamp` | Común a todas las entidades |
| Fecha/hora de recepción | — (la genera el colector) | `received_at` | UTC, tomada tras recibir la respuesta |
| *(extra)* Próxima parada | `vehicle.stopId` | `stop_id` | Falta en 9 de 155 trenes en la captura de referencia |
| *(extra)* Estado | `vehicle.currentStatus` | `status` | `STOPPED_AT` / `IN_TRANSIT_TO` |

---

## Decisiones de diseño

### Validación

| Caso | Tratamiento |
|---|---|
| Error de red, timeout, HTTP 4xx/5xx o JSON inválido | `fetch_feed` imprime el error y devuelve `None`; la lectura se omite y el bucle continúa. |
| Respuesta vacía o sin `entity` | Se procesa como 0 trenes, sin error. |
| Falta `vehicle_id`, latitud o longitud | La entidad se descarta con aviso. |
| Latitud fuera de [-90, 90] o longitud fuera de [-180, 180] | La entidad se descarta con aviso. |
| Coordenadas con valor `0` | Se consideran válidas: se comprueba `is None`, no "falsedad". |
| Campos opcionales ausentes (`tripId`, `stopId`, `currentStatus`) | Se guardan como `None` (acceso con `.get()`). |
| Falta `header.timestamp` | `position_timestamp = None`. |

### Deduplicación

Un mismo tren físico aparece varias veces en una lectura, una por cada `tripId` asociado (por ejemplo `1420212026-11-11`, `1420222026-11-11`...). En la captura de referencia, **204 entidades corresponden a 155 vehículos**.

- **Identificador de tren:** `vehicle.vehicle.id`. Es el campo que GTFS-RT define para el vehículo físico. `entity.id` identifica la entrada del mensaje, y `tripId` identifica el viaje, no el tren.
- **Regla:** si un `vehicle_id` se repite, se conserva **la última aparición**. El feed no incluye un timestamp por entidad, así que no hay un criterio de "más reciente". La regla es arbitraria pero determinista, y garantiza que cada tren se compare una sola vez.
- **Anomalía:** si los duplicados de un mismo `vehicle_id` traen **coordenadas distintas**, se imprime un `AVISO` con ambas posiciones en lugar de ocultarlo.

### Fechas

- Todas las fechas se manejan en **UTC** con zona horaria explícita (`datetime` *aware*).
- `position_timestamp` es cuándo dice Renfe que se tomaron las posiciones. `received_at` es cuándo las recibió el colector. Comparar ambas permite detectar datos con retraso.
- Todos los trenes de una misma lectura comparten el mismo `received_at`.

### Cálculo de alertas

- **Distancia:** fórmula de Haversine sobre una esfera de radio 6 371 000 m. Resultado en metros, redondeado a 1 decimal (la precisión GPS no justifica más).
- **Pares:** `itertools.combinations(trains, 2)`. Cada par se evalúa **una sola vez** (A-B, pero no B-A) y nunca un tren consigo mismo. Con *n* trenes son *n·(n−1)/2* comparaciones: ~12 000 para 155 trenes, unos 9 ms.
- **Condición:** `distancia < umbral`, estrictamente menor, como pide el enunciado.
- **Se comparan todos los pares**, sin filtrar por parada. Se valoró comparar solo trenes con el mismo `stopId`, pero se descartó:
  - el enunciado pide comparar cada tren con todos los demás;
  - `stopId` es la *próxima parada*, no la vía: dos trenes de frente en la misma vía tienen paradas distintas, y dos trenes que llegan a una estación desde lados opuestos comparten parada;
  - con los datos reales, **6 de las 7 alertas a 1000 m eran entre trenes con `stopId` distinto**, incluidos pares a 0 m.
- **Contexto en lugar de filtro:** cada alerta incluye `same_stop` y `both_stopped` para que la capa de visualización pueda distinguir, por ejemplo, "trenes parados en la misma estación" de "trenes en marcha cerca". Se guardan todos los datos y se filtra al consultar.

### Muestra anonimizada

[samples/vehicle_positions_sample.json](samples/vehicle_positions_sample.json) es una respuesta real del feed procesada con [make_sample.py](make_sample.py):

- Se sustituyen los identificadores de vehículo (`entity.id`, `vehicle.id`, `vehicle.label` y el prefijo de `tripId`) por IDs ficticios `T001`, `T002`...
- El **mismo id real recibe siempre el mismo id ficticio**, así que los duplicados se conservan.
- Se mantienen coordenadas, paradas, estados y timestamp: la muestra produce **las mismas 155 posiciones y 7 alertas** que la captura original.

Regenerarla a partir de otra captura:

```powershell
python make_sample.py data/<captura>.json samples/vehicle_positions_sample.json
```

---

## Limitaciones de los datos observadas

- **No hay ruta ni línea** (`routeId`) en el feed. El campo se omite.
- **No hay timestamp por vehículo**, solo uno común en la cabecera.
- **Retraso:** el `header.timestamp` puede ir por detrás de la hora real de recepción.
- **Trenes distintos en coordenadas idénticas.** Varios pares con `vehicle_id` diferente aparecen exactamente en el mismo punto (distancia 0,0 m). Probablemente sean composiciones acopladas o trenes parados con la coordenada de la estación. Generan alertas que no indican ninguna situación anómala.
- **La mayoría de alertas son trenes en estaciones:** en la captura de referencia, 5 de las 7 alertas a 1000 m eran entre dos trenes `STOPPED_AT`.
- **Un mismo `vehicle_id` en dos posiciones distintas** dentro de la misma lectura. Observado en datos reales con unos 30 km de separación. Se conserva la última posición y se emite un aviso.
- **`stopId` ausente** en una parte de los trenes, tanto parados como en marcha.
- **Alertas repetidas:** un par que sigue dentro del umbral genera una alerta en cada instantánea nueva del feed (ver [Deduplicación en la base de datos](#deduplicación-en-la-base-de-datos)).
- El esquema del feed puede cambiar sin aviso. El parser usa accesos tolerantes (`.get()`) y descarta lo que no puede validar.
