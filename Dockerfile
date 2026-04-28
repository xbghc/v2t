# Stage 1: 构建前端（pnpm workspace）
FROM node:22-alpine AS frontend-build
RUN npm install -g pnpm@10.30.0
WORKDIR /app
# 先只复制 manifest 让 pnpm install 可缓存
COPY pnpm-workspace.yaml pnpm-lock.yaml package.json .npmrc ./
COPY apps/web/package.json ./apps/web/
COPY packages/shared/package.json ./packages/shared/
RUN pnpm install --frozen-lockfile
# 再复制源码
COPY packages/shared ./packages/shared
COPY apps/web ./apps/web
RUN pnpm --filter @v2t/web build

# Stage 2: Python 后端（web + worker 共用）
# pin 到 bookworm（Debian 12），避免 trixie 上 ffmpeg 拖整个图形栈（mesa/llvm 等）
FROM python:3.12-slim-bookworm AS backend
# 切清华镜像源（buildkit 默认走 deb.debian.org 偏慢）
RUN sed -i 's|deb.debian.org|mirrors.tuna.tsinghua.edu.cn|g' \
        /etc/apt/sources.list.d/debian.sources \
        /etc/apt/sources.list 2>/dev/null || true \
    && apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg aria2 libatomic1 \
    && rm -rf /var/lib/apt/lists/*
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv
# 切清华 PyPI 镜像（uv 0.4+ 用 UV_DEFAULT_INDEX，老版本兼容 UV_INDEX_URL）
# UV_HTTP_TIMEOUT 加到 600s：torch / onnxruntime / pedalboard 都是大 wheel，
# 默认 30s 在国内并发拉取容易超时
ENV UV_DEFAULT_INDEX=https://pypi.tuna.tsinghua.edu.cn/simple \
    UV_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple \
    UV_HTTP_TIMEOUT=600
WORKDIR /app
COPY backend/pyproject.toml backend/uv.lock ./
# uv sync --frozen 严格按 lock 里写死的 URL 拉，不应用 UV_DEFAULT_INDEX。
# lock 里既有 simple index URL 也有 files.pythonhosted.org wheel URL，
# 都改写到清华镜像（hash 校验只看 sha256，不看 host，host 替换安全）。
# 阿里云 torch wheel 由 [tool.uv.sources] 锁定，不被影响。
RUN sed -i \
    -e 's|https://pypi\.org/simple|https://pypi.tuna.tsinghua.edu.cn/simple|g' \
    -e 's|https://files\.pythonhosted\.org/packages|https://pypi.tuna.tsinghua.edu.cn/packages|g' \
    uv.lock
RUN uv sync --frozen --no-dev
# 预热 silero-vad（验证 onnxruntime 可加载；模型文件已 bundled，不会下载）
RUN .venv/bin/python -c "from silero_vad import load_silero_vad; load_silero_vad(onnx=True)"
COPY backend/ ./
CMD [".venv/bin/uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8101"]

# Stage 3: Nginx + 前端静态文件
FROM nginx:alpine AS nginx
RUN rm /etc/nginx/conf.d/default.conf
COPY --from=frontend-build /app/apps/web/dist /usr/share/nginx/html
COPY deploy/nginx-docker.conf /etc/nginx/conf.d/default.conf
