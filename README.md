# v2t - 视频转文字工具

一键下载视频、转录音频、AI 生成摘要的 Web 应用。

## 特性

- **视频下载** - 支持 B站、抖音、小红书等平台，aria2c 多线程加速
- **音频转录** - 使用 Groq Whisper API 快速转录
- **AI 摘要** - 智能生成提纲与详细总结

## 安装

### 前置要求

- Python 3.12+
- [uv](https://github.com/astral-sh/uv)
- ffmpeg
- aria2

```bash
# macOS
brew install ffmpeg aria2

# Ubuntu/Debian
sudo apt install ffmpeg aria2
```

### 安装步骤

```bash
git clone https://github.com/user/v2t.git
cd v2t
uv sync
```

## 配置

配置 API Key（通过环境变量或配置文件 `~/.config/v2t/config.json`）：

- **OpenAI 兼容 API** - 用于 AI 内容生成（支持 DeepSeek、OpenAI、Ollama 等）
- **Whisper 兼容 API** - 用于语音转录（支持 Groq、OpenAI 等）
- **DashScope API Key** - https://dashscope.console.aliyun.com/ （TTS 语音合成，可选）
- **Xiazaitool Token** - 用于解析视频链接（可选）

环境变量：

```bash
# AI 内容生成
OPENAI_API_KEY=xxx
OPENAI_BASE_URL=https://api.deepseek.com  # 可选，默认 DeepSeek
OPENAI_MODEL=deepseek-reasoner             # 可选

# 语音转录
WHISPER_API_KEY=xxx
WHISPER_BASE_URL=https://api.groq.com/openai/v1  # 可选，默认 Groq
WHISPER_MODEL=whisper-large-v3                    # 可选

# 其他服务
DASHSCOPE_API_KEY=xxx
XIAZAITOOL_TOKEN=xxx
```

## 使用方法

### 本地运行

```bash
# 启动 Web 服务（默认端口 8100）
uv run v2t-web

# 或使用 uvicorn 自定义配置
uv run uvicorn app.web:app --host 0.0.0.0 --port 8100
```

然后在浏览器访问 http://localhost:8100

### 部署到服务器

#### 1. 安装依赖

```bash
# 安装系统依赖
sudo apt install ffmpeg aria2

# 克隆项目
git clone https://github.com/user/v2t.git
cd v2t

# 安装 uv（如未安装）
curl -LsSf https://astral.sh/uv/install.sh | sh

# 安装 Python 依赖
uv sync
```

#### 2. 配置 API

设置环境变量或创建配置文件 `~/.config/v2t/config.json`：

```json
{
  "groq_api_key": "your-groq-key",
  "deepseek_api_key": "your-deepseek-key"
}
```

#### 3. 使用 systemd 部署

```bash
# 编辑服务文件，修改路径和用户
sudo cp deploy/v2t.service /etc/systemd/system/

# 编辑配置
sudo nano /etc/systemd/system/v2t.service
# 修改:
#   User=你的用户名
#   WorkingDirectory=/你的项目路径
#   ExecStart=/你的项目路径/.venv/bin/uvicorn app.web:app --host 0.0.0.0 --port 8100

# 启动服务
sudo systemctl daemon-reload
sudo systemctl enable v2t
sudo systemctl start v2t

# 查看状态
sudo systemctl status v2t
```

#### 4. 配置 Nginx 反向代理（可选）

```nginx
server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://127.0.0.1:8100;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_read_timeout 300s;  # 视频处理可能耗时较长
    }
}
```

## License

MIT
