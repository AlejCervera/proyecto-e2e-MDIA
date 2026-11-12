from datetime import datetime, timezone
import requests

FEED_URL = "https://gtfsrt.renfe.com/vehicle_positions_LD.json"

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

# PROBAMOS SU CONEXION

if __name__ == "__main__":
    import json
    with open("data/vehicle_positions_LD.json", encoding="utf-8") as f:
        feed = json.load(f)

    received_at = datetime.now(timezone.utc)
    trains = parse_feed(feed, received_at)

    print(f"{len(feed['entity'])} entidades → {len(trains)} trenes únicos")
    print(trains[0])