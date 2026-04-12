# Stage 1: 构建前端
FROM node:22-alpine AS frontend-build
WORKDIR /app
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# Stage 2: Python 后端（web + worker 共用）
FROM python:3.12-slim AS backend
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg aria2 \
    && rm -rf /var/lib/apt/lists/*
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv
WORKDIR /app
COPY backend/pyproject.toml backend/uv.lock ./
RUN uv sync --frozen --no-dev
COPY backend/ ./
CMD [".venv/bin/uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8101"]

# Stage 3: Nginx + 前端静态文件
FROM nginx:alpine AS nginx
RUN rm /etc/nginx/conf.d/default.conf
COPY --from=frontend-build /app/dist /usr/share/nginx/html
COPY deploy/nginx-docker.conf /etc/nginx/conf.d/default.conf
