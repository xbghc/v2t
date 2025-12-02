# 使用 Python 3.12 作为基础镜像
FROM python:3.12-slim

# 设置工作目录
WORKDIR /app

# 设置环境变量
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_SYSTEM_PYTHON=1

# 安装系统依赖：ffmpeg 和 aria2
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    aria2 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# 安装 uv (先设置 PATH，确保后续命令可用)
ENV PATH="/root/.local/bin:$PATH"
RUN curl -LsSf https://astral.sh/uv/install.sh | sh

# 复制项目文件
COPY pyproject.toml ./
COPY app/ ./app/

# 安装 Python 依赖
RUN uv pip install .

# 创建输出目录
RUN mkdir -p /output

# 暴露 Web 服务端口
EXPOSE 8100

# 默认启动 Web 服务
CMD ["v2t-web"]
