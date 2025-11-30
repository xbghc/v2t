# v2t - 视频转文字工具

一键下载视频、转录音频、AI 生成摘要

```bash
$ v2t --summary "https://www.bilibili.com/video/BV1mb42177oQ"

下载视频...
✓ 【TED科普】为什么我们要跟陌生人闲聊？
转录音频...
✓ 转录完成
生成提纲...
✓ 已保存: 【TED科普】为什么我们要跟陌生人闲聊？_提纲.md
```

生成的提纲：

```markdown
### 视频大纲与时间线

**视频主题：** 日常简短对话的重要性与深层意义

#### 时间线：

- **[00:01 - 00:30]** 对短暂社交的质疑
  - 提出日常中与陌生人进行简短对话的场景
  - 质疑为何要在繁忙的生活中花费时间与陌生人交流

- **[00:31 - 00:54]** 简短对话的独特价值
  - 反驳上述观点，指出忽略简短社交的误区
  - 比喻：简短对话与长篇友谊的关系

- **[00:55 - 01:28]** 简短对话的情感力量
  - 指出简短对话对于缓解悲伤、自我怀疑的重要性

...
```

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

首次使用需配置 API Key：

```bash
uv run v2t config
```

需要以下凭证：
- **Xiazaitool Token** - 用于解析视频链接（必需）
- **Groq API Key** - https://console.groq.com/keys （用于语音转录）
- **GitCode AI Token** - https://ai.gitcode.com/ （用于 AI 摘要）

## 使用方法

```bash
# 生成 AI 详细总结 → .md
uv run v2t "视频链接"

# 生成提纲 → .md
uv run v2t "视频链接" --summary

# 仅输出原始转录 → .txt
uv run v2t "视频链接" --raw

# 仅下载视频
uv run v2t "视频链接" --video

# 仅提取音频
uv run v2t "视频链接" --audio
```

## 输出说明

| 模式 | 命令 | 输出 |
|------|------|------|
| 默认 | `v2t <url>` | `标题.md` - AI 详细总结 |
| 提纲 | `v2t <url> -s` | `标题_提纲.md` - 结构化提纲 |
| 原始 | `v2t <url> -r` | `标题.txt` - 带时间戳的转录 |
| 视频 | `v2t <url> -v` | `标题.mp4` - 仅下载视频 |
| 音频 | `v2t <url> -a` | `标题.mp3` - 仅提取音频 |

## Web 版本

v2t 支持 Web 界面，可以部署为网站使用。

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

```bash
uv run v2t config
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
