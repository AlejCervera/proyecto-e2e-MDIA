"""Genera una muestra anonimizada del feed a partir de una captura real.

Uso: python make_sample.py <entrada.json> <salida.json>

Sustituye los identificadores de vehiculo (y la parte del tripId que los contiene)
por IDs ficticios T001, T002... El mismo id real recibe siempre el mismo id ficticio,
asi que los duplicados del feed se conservan. Coordenadas, paradas, estados y
timestamp se mantienen para que la muestra siga generando las mismas alertas.
"""
import json
import sys

src, dst = sys.argv[1], sys.argv[2]

with open(src, encoding="utf-8") as f:
    feed = json.load(f)

new_ids = {}  # id real -> id ficticio (el mismo tren siempre recibe el mismo)

for entity in feed.get("entity", []):
    vehicle_block = entity.get("vehicle", {})
    descriptor = vehicle_block.get("vehicle", {})
    real_id = descriptor.get("id")
    if real_id is None:
        continue

    if real_id not in new_ids:
        new_ids[real_id] = f"T{len(new_ids) + 1:03d}"  # T001, T002, ...
    fake_id = new_ids[real_id]

    entity["id"] = f"VP_{fake_id}"
    descriptor["id"] = fake_id
    descriptor["label"] = fake_id

    trip = vehicle_block.get("trip", {})
    trip_id = trip.get("tripId")
    if trip_id and trip_id.startswith(real_id):
        trip["tripId"] = fake_id + trip_id[len(real_id):]  # cambia solo la parte del id

with open(dst, "w", encoding="utf-8") as f:
    json.dump(feed, f, indent=2, ensure_ascii=False)

print(f"{len(feed.get('entity', []))} entidades, {len(new_ids)} vehiculos anonimizados -> {dst}")
