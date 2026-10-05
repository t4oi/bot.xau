# XAUUSD Pro Signal Bot — Dockerfile
FROM python:3.11-slim

WORKDIR /app

# System deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc curl && rm -rf /var/lib/apt/lists/*

# Python deps
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Application
COPY . .

# Data & logs dirs
RUN mkdir -p data logs

ENV PYTHONUNBUFFERED=1
ENV TZ=UTC

EXPOSE 8080

HEALTHCHECK --interval=60s --timeout=10s --retries=3 \
    CMD python scripts/health_check.py || exit 1

CMD ["python", "run.py"]
