# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目概述

v2t 是一个视频转文字 Web 应用，提供视频下载、音频转录、AI内容生成功能。支持 B站、抖音、小红书等多平台。

## 项目结构 (Monorepo)

```
v2t/
├── backend/                    # Python 后端 (仅 API)
│   ├── app/
│   │   ├── web.py
│   │   ├── config.py
│   │   └── services/
│   ├── tests/
│   ├── pyproject.toml
│   └── pytest.ini
├── frontend/                   # Vue 前端
│   ├── src/
│   │   └── router/            # Vue Router 路由
│   ├── dist/                  # 前端构建输出
│   ├── package.json
│   └── vite.config.ts
├── Makefile                    # 根级构建脚本
├── Dockerfile
├── docker-compose.yml
└── deploy/
    ├── v2t.service            # systemd 服务
    └── nginx-local.conf       # 本地 nginx 配置
```

## 常用命令

### 使用 Makefile（推荐）

```bash
make install              # 安装所有依赖
make dev                  # 同时启动前后端开发服务器
make dev-backend          # 仅启动后端 (端口 8101)
make dev-frontend         # 仅启动前端开发服务器
make build                # 构建前端到 frontend/dist/
make test                 # 运行测试
make lint                 # 运行 lint 检查
make lint-fix             # 自动修复 lint 问题
```

### 后端 (backend/)

```bash
cd backend
uv sync                          # 安装依赖
uv run v2t-web                   # 启动Web服务 (端口8101，仅API)
pytest                           # 运行测试
```

### 前端 (frontend/)

```bash
cd frontend
npm install                      # 安装依赖
npm run dev                      # 开发服务器 (Vite，代理 /api 到 8100)
npm run build                    # 构建到 frontend/dist/
```

### Docker

```bash
docker build -t v2t:latest .
docker-compose up -d
```

## 架构概览

### 后端分层 (Python)

```
backend/app/
├── web.py          # Web入口 (FastAPI)，后台任务+内存存储
├── config.py       # 配置管理 (环境变量 > JSON文件 > 默认值)
└── services/       # 业务服务层
    ├── xiazaitool.py       # 视频链接解析 (外部API)
    ├── video_downloader.py # 视频下载 (aria2c)
    ├── transcribe.py       # 音频转录 (Whisper 兼容 API)
    ├── llm.py              # AI生成 (OpenAI 兼容 API)
    └── podcast_tts.py      # 播客音频合成 (阿里云百炼 TTS)
```

**全异步架构**：所有 I/O 操作使用 `async/await`，外部命令通过 `asyncio.create_subprocess_exec` 执行。

**Web 任务状态流转**：
```
PENDING → DOWNLOADING → TRANSCRIBING → GENERATING → COMPLETED/FAILED
```

### 前端架构 (Vue 3 + Vite + Vue Router)

```
frontend/src/
├── router/index.ts   # Vue Router 路由配置
├── stores/task.ts    # Pinia状态管理 (集中管理所有任务状态，不操作路由)
├── api/task.ts       # API调用模块
└── components/       # Vue组件
```

**路由**：使用 Vue Router，路径 `/` (首页) 和 `/task/:id` (结果页)。

**轮询机制**：任务创建后，2 秒间隔轮询 `/api/task/{id}` 直到完成或失败。

### 关键依赖

- **系统**：ffmpeg (音频提取)、aria2c (多线程下载)
- **外部服务**：Whisper 兼容 API (转录)、OpenAI 兼容 API (内容生成)、阿里云百炼 (TTS)、Xiazaitool (链接解析)

## 环境变量

```bash
# OpenAI 兼容 API (AI 内容生成)
OPENAI_API_KEY       # API 密钥
OPENAI_BASE_URL      # API 端点 (默认: https://api.deepseek.com)
OPENAI_MODEL         # 模型名称 (默认: deepseek-reasoner)

# Whisper 兼容 API (语音转录)
WHISPER_API_KEY      # API 密钥
WHISPER_BASE_URL     # API 端点 (默认: https://api.groq.com/openai/v1)
WHISPER_MODEL        # 模型名称 (默认: whisper-large-v3)

# 其他服务
DASHSCOPE_API_KEY    # 阿里云百炼 API (TTS 语音合成)
XIAZAITOOL_TOKEN     # 视频链接解析 API
```

配置文件路径：`~/.config/v2t/config.json`

## API 端点

```
POST /api/process           # 创建任务 {url, download_only}
GET  /api/task/{task_id}    # 查询任务状态和结果
GET  /api/task/{task_id}/video  # 下载视频
GET  /api/task/{task_id}/audio  # 下载音频
```

## 错误处理

每个服务模块定义自己的异常类：`DownloadError`、`TranscribeError`、`LLMError`、`XiazaitoolError`。

AI 生成失败时自动降级到原始转录内容。

## 部署架构

```
浏览器 → nginx(8100) → 后端API(8101)
              ↓
     静态文件 (frontend/dist/)
```

- **nginx** (端口 8100)：提供静态文件 + SPA fallback，代理 `/api/` 到后端
- **后端** (端口 8101)：仅提供 API 服务，不处理静态文件

配置文件：`deploy/nginx-local.conf`
