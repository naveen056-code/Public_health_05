FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py .
COPY ui ./ui
COPY agent ./agent

ENV PORT=8080
ENV GOOGLE_GENAI_USE_VERTEXAI=TRUE
ENV GOOGLE_CLOUD_LOCATION=global

EXPOSE 8080

CMD exec uvicorn app:app --host 0.0.0.0 --port ${PORT:-8080}
