# Catch-a-Scammer in one image: the FastAPI server, which also serves the built
# React game. Used by deploy/compose.yml; see docs/DEPLOY.md.

# 1. build the React client
FROM node:22-slim AS client
WORKDIR /src/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ ./
RUN npm run build

# 2. the Python API, serving the client from /app/frontend/dist
FROM python:3.13-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app/backend
COPY backend/server/requirements.txt server/requirements.txt
RUN pip install --no-cache-dir -r server/requirements.txt
COPY backend/ ./
COPY --from=client /src/frontend/dist /app/frontend/dist
COPY deploy/entrypoint.sh /app/entrypoint.sh
RUN useradd --system --no-create-home app
USER app
EXPOSE 8000
ENTRYPOINT ["sh", "/app/entrypoint.sh"]
