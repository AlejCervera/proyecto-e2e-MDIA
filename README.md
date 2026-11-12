# RENFE — Alerta de proximidad entre trenes

## Descripción

En este ejercicio construiremos un pipeline para capturar y analizar las posiciones GPS de trenes de Alta Velocidad, Larga Distancia y Media Distancia de Renfe. El sistema permitirá configurar una distancia mínima y generará una alerta cuando dos trenes distintos estén a menos de ese valor.

La fuente publica posiciones en tiempo real y se actualiza aproximadamente cada 15 segundos. El conjunto incluye recursos JSON y Protocol Buffers; para el ejercicio comenzaremos con JSON.

- [Conjunto de datos: Posición vehículos AV, LD y MD](https://data.renfe.com/dataset/posicion-vehiculos-av-ld-md)
- Recurso JSON: <https://gtfsrt.renfe.com/vehicle_positions_LD.json>
- Recurso Protocol Buffers: <https://gtfsrt.renfe.com/vehicle_positions_LD.pb>

La disponibilidad y el esquema exacto del recurso pueden cambiar. El alumnado deberá inspeccionar la respuesta actual y adaptar el parser a sus campos. Si el recurso requiere cabeceras, formato o una ruta alternativa, documentar ese ajuste en el proyecto.

## Instrucciones

- La lógica de captura y alertas debe implementarse en Python.
- La solución final debe levantarse con `docker compose up`.
- El frontend puede utilizar la tecnología que el alumno elija con ayuda de una herramienta de IA.
- No se deben guardar credenciales ni datos sensibles en el repositorio.
- Configurar el umbral de proximidad mediante una variable de entorno, por ejemplo `ALERT_DISTANCE_METERS`.
- La distancia entre coordenadas se calculará en metros con una fórmula geodésica como Haversine.
- Cada tren se debe comparar una sola vez con los demás en cada lectura. No generar una alerta al comparar un tren consigo mismo.
- Incluir en cada alerta la identificación disponible de ambos trenes, sus coordenadas, la distancia calculada y la hora de captura.
- La alerta se produce solo cuando la distancia es estrictamente menor que el umbral configurado.
- Tener en cuenta que las posiciones son datos operativos orientativos y pueden tener retraso o imprecisión GPS. El ejercicio no debe presentar las alertas como un sistema de seguridad ferroviaria.

## Objetivos

1. Consumir una API de datos abiertos en tiempo real.
2. Inspeccionar y validar datos JSON externos.
3. Calcular distancias geográficas y aplicar una regla configurable.
4. Contenerizar el colector y persistir datos en SQL.
5. Construir una aplicación web que muestre posiciones y alertas recientes.

## Fase 1: consumo de API y alertas en Python

Crear `renfe_collector.py` para consultar desde un equipo local el recurso JSON y generar alertas cuando dos trenes estén a menos del umbral configurado. Como la fuente anuncia actualizaciones cada 15 segundos, se recomienda no consultar más rápido que esa frecuencia.

El parser debe extraer, cuando estén disponibles:

- Identificador o matrícula del vehículo
- Latitud y longitud
- Ruta, línea o servicio
- Identificador del viaje
- Fecha/hora de la posición
- Fecha/hora de recepción por el colector

El formato del feed puede seguir GTFS Realtime y cambiar. Validar campos ausentes, coordenadas fuera de rango, respuestas vacías, errores HTTP y registros duplicados. Conservar un ejemplo anonimizado de respuesta para facilitar el desarrollo sin conexión.

La fase se considera completada cuando el alumno puede ejecutar el script en local, ver las posiciones leídas y comprobar una alerta con un umbral en metros configurable.

## Fase 2: dockerizar la solución Python

Crear un `Dockerfile` para instalar dependencias y ejecutar el colector y el cálculo de proximidad dentro de un contenedor. Pasar el umbral y la frecuencia de consulta como variables de entorno, y documentar cómo construir y ejecutar la imagen.

La lógica que funcionó en local en la fase anterior debe ejecutarse dentro del contenedor sin depender del entorno Python del host.

## Fase 3: almacenamiento SQL con Docker Compose

Añadir una base de datos SQL al proyecto y guardar las posiciones y alertas. Usar Docker Compose para definir al menos el servicio del colector y el de la base de datos, con persistencia mediante un volumen.

Propuesta inicial de tabla para las posiciones:

```sql
CREATE TABLE train_positions (
    id BIGSERIAL PRIMARY KEY,
    vehicle_id TEXT NOT NULL,
    trip_id TEXT,
    route_id TEXT,
    latitude DOUBLE PRECISION NOT NULL,
    longitude DOUBLE PRECISION NOT NULL,
    position_timestamp TIMESTAMPTZ,
    received_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    raw_payload JSONB
);
```

Diseñar también una tabla para las alertas que registre ambos trenes, la distancia observada, las coordenadas y las marcas temporales. Añadir índices adecuados para consultar las posiciones recientes por vehículo y las alertas por fecha. Documentar las decisiones de deduplicación y los tipos de fecha/hora.

El colector debe escribir en SQL las lecturas y alertas, y la configuración de conexión debe realizarse mediante variables de entorno.

## Fase 4: ejecución automática

Completar `docker-compose.yml` para que un único comando levante toda la solución:

```bash
docker compose up
```

La base de datos debe estar lista antes de que el colector intente conectarse. El proceso Python debe arrancar automáticamente, capturar datos de forma continua y generar alertas sin pasos manuales adicionales. Documentar cómo configurar el umbral y cómo consultar los logs.

## Fase 5: backend con FastAPI

Crear un backend en Python con FastAPI en un contenedor independiente. El backend consultará la base de datos y expondrá una API para el frontend. La documentación interactiva de Swagger debe estar disponible en `/docs`.

Implementar como mínimo estos endpoints:

- `GET /getAlertas`: devuelve las alertas registradas, incluyendo identificadores de trenes, distancia, umbral y fecha/hora. Permite limitar la cantidad de resultados y ordenarlos de más recientes a más antiguos.
- `GET /getTren/{id}`: devuelve los datos y la posición más reciente del tren indicado. Responder con `404` si no existe.
- `GET /getDistancia/{trenId1}/{trenId2}`: calcula y devuelve la distancia actual en metros entre las posiciones más recientes de los dos trenes. Validar que ambos trenes existan y que sus posiciones sean recientes.

El backend debe leer la configuración de conexión mediante variables de entorno, manejar errores de base de datos y validar las respuestas con modelos de FastAPI/Pydantic. Añadir el servicio del backend a Docker Compose con dependencia de la base de datos.

## Fase 6: frontend asistido por IA

Con ayuda de una herramienta de IA, generar un frontend que se conecte a la solución y consulte la base de datos a través de una API backend. No conectar el navegador directamente a SQL ni exponer credenciales de base de datos.

El frontend debe mostrar:

- Las posiciones recientes de los trenes, con identificación y coordenadas disponibles.
- Las alertas recientes, indicando los trenes, la distancia medida, el umbral configurado y la hora.
- Actualización en tiempo real o sondeo periódico de la API para reflejar nuevos datos.
- Un estado claro cuando no haya datos recientes o el servicio no esté disponible.

Añadir el frontend a Docker Compose y conectarlo a los endpoints FastAPI. Toda la aplicación debe poder iniciarse con `docker compose up`. Se permite utilizar IA para generar la interfaz, pero el alumno debe revisar, comprender y documentar el código resultante.

## Entregables

- Script Python que lea datos locales de la API y genere alertas con un umbral configurable.
- `Dockerfile` y `docker-compose.yml` para el colector, la base SQL, el backend FastAPI y el frontend.
- Esquema SQL para almacenar posiciones y alertas, con persistencia de datos.
- Backend FastAPI con Swagger y los endpoints mínimos `getAlertas`, `getTren(id)` y `getDistancia(trenId1, trenId2)`.
- Frontend que muestre trenes y alertas recientes.
- `README` con configuración, instrucciones de ejecución con `docker compose up`, ejemplo de alerta y limitaciones de los datos.
