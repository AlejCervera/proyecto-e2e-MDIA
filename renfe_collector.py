from datetime import datetime, timezone
import requests

FEED_URL = "https://gtfsrt.renfe.com/vehicle_positions_LD.json"

def fetch_feed(url):
    """Descarga el feed y devuelve el JSON como dict, o None si algo falla."""
    # TODO 1: hacer un GET con requests, con un timeout de ~10 segundos
    # TODO 2: si el código HTTP no es 2xx, que salte un error (busca qué hace response.raise_for_status())
    # TODO 3: convertir la respuesta a dict (response.json())
    # TODO 4: envolver todo en try/except para capturar errores de red y de JSON,
    #         imprimir un mensaje claro y devolver None
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"ERROR al descargar el feed: {e}")
        return None

if __name__ == "__main__":
    feed = fetch_feed(FEED_URL)
    print(len(feed["entity"]) if feed else "sin datos")

