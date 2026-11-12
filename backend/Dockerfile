# Imagen del backend FastAPI.
# Se construye con el contexto en la raíz del repo (para poder copiar geo.py):
#   docker build -f backend/Dockerfile -t renfe-backend .
FROM python:3.13-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY geo.py .
COPY backend/ backend/

RUN useradd --create-home appuser
USER appuser

EXPOSE 8000

CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
