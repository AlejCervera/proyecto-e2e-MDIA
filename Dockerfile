# Imagen base: Linux mínimo con Python 3.13 (la misma versión que el .venv local)
FROM python:3.13-slim

# Sin buffer en stdout: los print() aparecen al momento en `docker logs`
# Sin .pyc: no tiene sentido generarlos dentro del contenedor
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# Carpeta de trabajo dentro del contenedor
WORKDIR /app

# 1º las dependencias: esta capa se cachea y solo se rehace si cambia requirements.txt
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 2º el código (cambia a menudo, por eso va después)
COPY renfe_collector.py storage.py geo.py ./
COPY samples/ samples/

# Valores por defecto de la configuración (se sobrescriben con `docker run -e`)
ENV ALERT_DISTANCE_METERS=1000 \
    POLL_INTERVAL_SECONDS=15

# No ejecutar como root dentro del contenedor
RUN useradd --create-home appuser
USER appuser

CMD ["python", "renfe_collector.py"]
