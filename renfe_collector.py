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
        "stop_id": vehicle_block.get("stopID"),      # sácalo de vehicle_block
        "status": vehicle_block.get("currentStatus"),       # currentStatus
        "latitude": lat,
        "longitude": lon,
    }

# PROBAMOS SU CONEXION

if __name__ == "__main__":
    import json
    with open("data/vehicle_positions_LD.json", encoding="utf-8") as f:
        feed = json.load(f)

    for entity in feed["entity"][:5]:
        print(parse_entity(entity))

    print(parse_entity({}))
    print(parse_entity({"vehicle": {"vehicle": {"id": "X"}, "position": {"latitude": 95, "longitude": 2}}}))
    print(parse_entity({"vehicle": {"vehicle": {"id": "Y"}, "position": {"latitude": 0, "longitude": 0}}}))
