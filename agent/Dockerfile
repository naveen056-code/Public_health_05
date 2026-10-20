# Serves main.py: ADK's API, our interface at /, and ADK's developer UI at /dev-ui/.
# Build context is this folder:  gcloud run deploy clinic-broker --source agent ...
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /app

COPY clinic_broker/requirements.txt clinic_broker/requirements.txt
RUN pip install -r clinic_broker/requirements.txt

COPY . .
RUN useradd --create-home app && chown -R app /app
USER app

CMD exec uvicorn main:app --host 0.0.0.0 --port ${PORT:-8080}
