# Gist · 视频预审工具

刷到一个视频，拿不准要不要看完？先用 Gist 抓个大意。一键下载视频、转录音频、AI 生成要点摘要，让你在投入时间前就看清这视频值不值得。支持 B 站、抖音、小红书等平台。

## 快速开始（Docker）

```bash
# 1. 克隆项目
git clone https://github.com/xbghc/v2t.git
cd v2t

# 2. 配置环境变量
cp backend/.env.example .env
# 编辑 .env，填入 API Key

# 3. 启动
docker compose up -d

# 4. 访问
open http://localhost:8100
```

## 环境变量

```bash
# AI 内容生成 (OpenAI 兼容)
OPENAI_API_KEY=xxx
OPENAI_BASE_URL=https://api.deepseek.com    # 支持 DeepSeek、OpenAI 等
OPENAI_MODEL=deepseek-reasoner

# 语音转录 (OpenAI Whisper 兼容: Groq、OpenAI、自托管 Qwen3-ASR 等)
WHISPER_API_KEY=xxx
WHISPER_BASE_URL=xxx                         # 必填，无默认值
WHISPER_MODEL=xxx

# 其他服务
XIAZAITOOL_TOKEN=xxx                         # 视频链接解析
DASHSCOPE_API_KEY=xxx                        # TTS 语音合成（可选）
```

## 架构

```
Docker Compose 编排 4 个服务：

nginx (8100)  ──→  web (FastAPI)  ──→  Redis
                   worker (arq)   ──→  Redis

- nginx: 前端静态文件 + API 反代
- web: FastAPI 后端 API
- worker: arq 异步任务（视频下载、音频转录）
- redis: 任务队列 + 元数据存储 + Pub/Sub
```

## 本地开发

### 前置要求

- Python 3.12+、[uv](https://github.com/astral-sh/uv)、Node.js 22+
- ffmpeg、aria2
- Redis

```bash
# macOS
brew install ffmpeg aria2 redis

# Ubuntu/Debian
sudo apt install ffmpeg aria2 redis-server
```

### 开发命令

```bash
make install          # 安装所有依赖
make backend          # 启动后端 (端口 8103)
make worker           # 启动 arq worker
make frontend         # 启动前端开发服务器
make test             # 运行测试
make lint             # 运行 lint 检查
```

### Docker 命令

```bash
make docker-build     # 构建镜像
make docker-up        # 启动所有服务
make docker-down      # 停止所有服务
make docker-logs      # 查看日志
```

## License

MIT
