from datetime import datetime, timezone
from math import radians, sin, cos, asin, sqrt
import requests
import os 
from itertools import combinations
import json

FEED_URL = "https://gtfsrt.renfe.com/vehicle_positions_LD.json"
EARTH_RADIUS_M = 6_371_000

# VARIABLES DE ENTORNO

ALERT_DISTANCE_METERS = float(os.getenv("ALERT_DISTANCE_METERS", "1000"))
POLL_INTERVAL_SECONDS = int(os.getenv("POLL_INTERVAL_SECONDS", "15"))
POLL_INTERVAL_SECONDS = max(POLL_INTERVAL_SECONDS, 15)  # nunca más rápido que el feed
FEED_FILE = os.getenv("FEED_FILE")  # si se define, se lee este fichero en vez de la API

# DISTANCIA ENTRE DOS PUNTOS

def haversine_m(lat1, lon1, lat2, lon2):
    """Distancia en metros entre dos puntos (lat, lon) expresados en grados."""
    phi1, phi2 = radians(lat1), radians(lat2)
    dphi = radians(lat2 - lat1)
    dlambda = radians(lon2 - lon1)

    a = sin(dphi / 2) ** 2 + cos(phi1) * cos(phi2) * sin(dlambda / 2) ** 2
    return 2 * EARTH_RADIUS_M * asin(sqrt(a))

# NOS CONECTAMOS A LA API

def fetch_feed(url):
    """Descarga el feed y devuelve el JSON como dict, o None si algo falla."""
    # 1: hacer un GET con requests, con un timeout de ~10 segundos
    # 2: si el código HTTP no es 2xx, que salte un error (busca qué hace response.raise_for_status())
    # 3: convertir la respuesta a dict (response.json())
    # 4: envolver todo en try/except para capturar errores de red y de JSON,
    #         imprimir un mensaje claro y devolver None
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"ERROR al descargar el feed: {e}")
        return None

def load_feed():
    """Obtiene el feed: desde FEED_FILE si está definido, o desde la API si no."""
    if FEED_FILE:
        try:
            with open(FEED_FILE, encoding="utf-8") as f:
                return json.load(f)
        except (OSError, json.JSONDecodeError) as e:
            print(f"ERROR al leer {FEED_FILE}: {e}")
            return None
    return fetch_feed(FEED_URL)


#LIMPIAMOS EL JSON

def parse_entity(entity):
    """Convierte una entidad del feed en un dict limpio, o None si no es válida."""
    vehicle_block = entity.get("vehicle") or {}
    position = vehicle_block.get("position") or {}
    trip = vehicle_block.get("trip") or {}
    descriptor = vehicle_block.get("vehicle") or {}

    vehicle_id = descriptor.get("id")
    lat = position.get("latitude")
    lon = position.get("longitude")

    # si falta vehicle_id, lat o lon → imprimir un aviso y devolver None
    #         (sin estos tres datos no podemos calcular distancias)
    if vehicle_id is None or lon is None or lat is None:
        print("Falta un dato clave para calcular")   
        return None 
    # si lat no está entre -90 y 90, o lon entre -180 y 180 → aviso y None
    if lat > 90 or lat < -90:
        print("Coordenadas incorrectas")
        return None
    elif lon > 180 or lon < -180:
        print("Coordenadas incorrectas")
        return None     

    return {
        "vehicle_id": vehicle_id,
        "trip_id": trip.get("tripId"),     # sácalo de trip (puede faltar → None)
        "stop_id": vehicle_block.get("stopId"),      # sácalo de vehicle_block
        "status": vehicle_block.get("currentStatus"),       # currentStatus
        "latitude": lat,
        "longitude": lon,
    }

def parse_feed(feed, received_at):
    """Devuelve una lista de trenes limpios y sin duplicados (uno por vehicle_id)."""
    trains = {}
    header = feed.get("header") or {}
    raw_ts = header.get("timestamp")

    # si raw_ts es None → position_timestamp = None
    # si no → convertirlo a datetime UTC (ya lo hiciste en el primer ejercicio)

    if raw_ts is None:
        position_timestamp = None
    else:
        position_timestamp = datetime.fromtimestamp(int(raw_ts), tz = timezone.utc) 

    for entity in feed.get("entity") or []:

        train = parse_entity(entity)
        # si train es None, saltar a la siguiente entidad
        if train is None:
            continue

        vid = train["vehicle_id"]
        # si vid ya está en trains Y (su lat es distinta O su lon es distinta)
        # → print(f"AVISO: ...") indicando el id y las dos posiciones
        if vid in trains and (train["latitude"] != trains[vid]["latitude"] or train["longitude"] != trains[vid]["longitude"]):
            print(f"AVISO: tren {vid} duplicado con posiciones distintas: "
                  f"({trains[vid]['latitude']}, {trains[vid]['longitude']}) vs "
                  f"({train['latitude']}, {train['longitude']})")

        train["position_timestamp"] = position_timestamp
        train["received_at"] = received_at
        trains[vid] = train

    return list(trains.values())

def find_alerts(trains, threshold_m):
    """Devuelve una lista de alertas para cada par de trenes a menos de threshold_m metros."""
    alerts = []
    for a, b in combinations(trains, 2):
        distance = haversine_m(a["latitude"], a["longitude"], b["latitude"], b["longitude"])

        if distance < threshold_m:
            alerts.append({
                "train_a": a["vehicle_id"],
                "lat_a": a["latitude"],
                "lon_a": a["longitude"],
                "train_b": b["vehicle_id"],
                "lat_b": b["latitude"],
                "lon_b": b["longitude"],
                "distance_m": round(distance, 1),
                "threshold_m": threshold_m,
                "position_timestamp": a["position_timestamp"],
                "detected_at": a["received_at"],
                "same_stop": a["stop_id"] is not None and a["stop_id"] == b["stop_id"],
                "both_stopped": a["status"] == "STOPPED_AT" and b["status"] == "STOPPED_AT"
            })
    return alerts

def run_once(threshold_m):
    """Hace una lectura completa: descarga, parsea, busca alertas e imprime el resultado."""
    feed = load_feed()
    if feed is None:
        print("Lectura omitida: no se pudo obtener el feed.")
        return

    # La hora se toma DESPUÉS de descargar: es el momento real en que recibimos los datos
    received_at = datetime.now(timezone.utc)

    trains = parse_feed(feed, received_at)
    alerts = find_alerts(trains, threshold_m)

    print(f"\n[{received_at:%Y-%m-%d %H:%M:%S} UTC] {len(trains)} trenes, {len(alerts)} alertas")

    # Muestra algunas posiciones leídas (el README pide "ver las posiciones")
    for t in trains[:5]:
        print(f"  tren {t['vehicle_id']}: ({t['latitude']}, {t['longitude']}) "
              f"{t['status']} → parada {t['stop_id']}")
    if len(trains) > 5:
        print(f"  ... y {len(trains) - 5} más")

    for a in alerts:
        print(f"  ALERTA: {a['train_a']} ↔ {a['train_b']} a {a['distance_m']} m "
              f"(umbral {a['threshold_m']} m)")

# PROBAMOS SU CONEXION

if __name__ == "__main__":
    import time

    print(f"Colector iniciado: umbral {ALERT_DISTANCE_METERS} m, cada {POLL_INTERVAL_SECONDS} s")
    print("Pulsa Ctrl+C para detener.")
    try:
        while True:
            run_once(ALERT_DISTANCE_METERS)
            time.sleep(POLL_INTERVAL_SECONDS)
    except KeyboardInterrupt:
        print("\nColector detenido.")


