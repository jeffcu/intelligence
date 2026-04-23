# ── Stage 1: build the React frontend ────────────────────────────────────────
FROM node:20-alpine AS frontend
WORKDIR /app
COPY package.json package-lock.json* ./
RUN npm ci
COPY index.html vite.config.js ./
COPY src ./src
RUN npm run build

# ── Stage 2: Python API + built frontend ─────────────────────────────────────
FROM python:3.11-slim
WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# API source files
COPY api.py summarizer.py ingestor.py news_scheduler.py .env* ./

# Built frontend
COPY --from=frontend /app/dist ./dist

# Startup script
COPY entrypoint.sh .
RUN chmod +x entrypoint.sh

# Persistent data volume — DB and chroma live here
VOLUME /app/data
ENV DATA_DIR=/app/data

EXPOSE 8001
ENTRYPOINT ["./entrypoint.sh"]
