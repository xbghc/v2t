# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目概述

v2t 是一个视频转文字工具，提供视频下载、音频转录、AI内容生成功能。支持 B站、抖音、小红书等多平台，提供 CLI 和 Web 两种使用方式。

## 常用命令

### Python (uv 包管理器)

```bash
uv sync                          # 安装依赖
uv run v2t <url>                 # CLI处理视频
uv run v2t config                # 交互式配置
uv run v2t-web                   # 启动Web服务 (端口8100)
```

### 前端 (frontend/)

```bash
npm install                      # 安装依赖
npm run dev                      # 开发服务器 (Vite，代理 /api 到 8100)
npm run build                    # 构建到 app/static/
```

### 测试

```bash
pytest                           # 运行所有测试
pytest tests/test_downloader.py  # 运行单个测试文件
pytest -v                        # 详细输出
```

### Docker

```bash
docker build -t v2t:latest .
docker-compose up -d
```

## 架构概览

### 后端分层 (Python)

```
app/
├── cli.py          # CLI入口 (Typer)
├── web.py          # Web入口 (FastAPI)，后台任务+内存存储
├── config.py       # 配置管理 (环境变量 > JSON文件 > 默认值)
└── services/       # 业务服务层
    ├── xiazaitool.py       # 视频链接解析 (外部API)
    ├── video_downloader.py # 视频下载 (aria2c)
    ├── transcribe.py       # 音频转录 (Groq Whisper)
    └── gitcode_ai.py       # AI生成 (GitCode API)
```

**全异步架构**：所有 I/O 操作使用 `async/await`，外部命令通过 `asyncio.create_subprocess_exec` 执行。

**Web 任务状态流转**：
```
PENDING → DOWNLOADING → TRANSCRIBING → GENERATING → COMPLETED/FAILED
```

### 前端架构 (Vue 3 + Vite)

```
frontend/src/
├── stores/task.js    # Pinia状态管理 (集中管理所有任务状态)
├── api/task.js       # API调用模块
└── components/       # Vue组件
```

**页面切换**：`page: 'initial' | 'result'`，通过 `v-if` 条件渲染。

**轮询机制**：任务创建后，2 秒间隔轮询 `/api/task/{id}` 直到完成或失败。

### 关键依赖

- **系统**：ffmpeg (音频提取)、aria2c (多线程下载)
- **外部服务**：Groq Whisper (转录)、GitCode AI (内容生成)、Xiazaitool (链接解析)

## 环境变量

```bash
GROQ_API_KEY         # Groq Whisper API
GITCODE_AI_TOKEN     # GitCode AI API
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

每个服务模块定义自己的异常类：`DownloadError`、`TranscribeError`、`GitCodeAIError`、`XiazaitoolError`。

AI 生成失败时自动降级到原始转录内容。
