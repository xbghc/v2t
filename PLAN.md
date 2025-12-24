# REST API 原子性改进计划

## 一、设计理念

### 从 Task 到 Resource

| 原设计 | 新设计 |
|--------|--------|
| `task_id` 管理一切 | `transcript` 是核心资源 |
| 一次性启动全流程 | 用户决定每一步 |
| 内存存储 | SQLite 持久化 |
| 轮询 task 状态 | SSE 实时推送状态 |

### 核心原则

1. **资源导向**: transcript 是核心资源，video 是可选输入源，outline/article 依赖 transcript
2. **原子操作**: 每个 API 只做一件事
3. **持久化**: 使用 SQLite 存储，服务重启不丢失数据
4. **实时推送**: 使用 SSE 推送进度，支持断线重连
5. **可重试**: 每个步骤可独立重试

---

## 二、数据库设计 (SQLite + aiosqlite)

### 技术选型

- **原生 sqlite3 + aiosqlite**: 轻量，无额外依赖，适合简单 CRUD
- **不使用 SQLAlchemy**: 项目简单，ORM 过度工程

### 表结构

```sql
-- 视频资源
CREATE TABLE videos (
    id TEXT PRIMARY KEY,              -- 8位UUID
    original_url TEXT,                -- 用户输入的原始链接
    normalized_url TEXT UNIQUE,       -- 规范化后的唯一标识（去除参数）
    download_url TEXT,                -- 解析得到的下载链接
    title TEXT,                       -- 视频标题
    status TEXT DEFAULT 'pending',    -- pending|downloading|completed
    video_path TEXT,                  -- 视频文件路径
    audio_path TEXT,                  -- 音频文件路径
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 转录资源（核心，video_id 可选）
CREATE TABLE transcripts (
    id TEXT PRIMARY KEY,
    video_id TEXT REFERENCES videos(id) ON DELETE SET NULL,  -- 可选，支持独立转录
    status TEXT DEFAULT 'pending',    -- pending|processing|completed
    content TEXT,                     -- 转录内容
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 大纲资源（依赖转录）
CREATE TABLE outlines (
    id TEXT PRIMARY KEY,
    transcript_id TEXT NOT NULL REFERENCES transcripts(id) ON DELETE CASCADE,
    status TEXT DEFAULT 'pending',    -- pending|processing|completed
    content TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 文章资源（依赖转录）
CREATE TABLE articles (
    id TEXT PRIMARY KEY,
    transcript_id TEXT NOT NULL REFERENCES transcripts(id) ON DELETE CASCADE,
    status TEXT DEFAULT 'pending',    -- pending|processing|completed
    content TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 索引
CREATE INDEX idx_videos_normalized_url ON videos(normalized_url);
CREATE INDEX idx_transcripts_video_id ON transcripts(video_id);
CREATE INDEX idx_outlines_transcript_id ON outlines(transcript_id);
CREATE INDEX idx_articles_transcript_id ON articles(transcript_id);
```

### URL 规范化

```python
from urllib.parse import urlparse

def normalize_url(url: str) -> str:
    """去除 URL 参数，返回规范化的唯一标识"""
    parsed = urlparse(url)
    return f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
```

**示例**:
| 原始 URL | 规范化后 |
|----------|----------|
| `https://bilibili.com/video/BV123?spm=xxx` | `https://bilibili.com/video/BV123` |
| `https://bilibili.com/video/BV123?t=120` | `https://bilibili.com/video/BV123` |

**API 行为**:
- POST 时先规范化 URL，查询是否已存在
- 已存在且完成 → 返回已有记录
- 已存在但处理中 → 返回已有记录（前端订阅 SSE）
- 不存在 → 创建新记录

### 错误处理策略

- **失败时不入库**: 操作失败时，不插入/更新数据库记录
- **API 返回实际错误**: 后端向前端返回具体错误信息
- **用户重试**: 前端显示错误后，用户可重新发起请求

### 状态枚举

| 状态 | 说明 |
|------|------|
| `pending` | 等待处理 |
| `downloading` | 下载中（仅 videos） |
| `processing` | 处理中 |
| `completed` | 完成 |

> 注：无 `failed` 状态，失败时记录不入库，API 直接返回错误

---

## 三、API 设计

### 端点概览

```
# 视频资源
POST   /api/videos                  # 创建视频（开始下载）
GET    /api/videos/{id}             # 获取视频状态（用于断线重连）
GET    /api/videos/{id}/events      # SSE 订阅下载进度
DELETE /api/videos/{id}             # 删除视频及所有派生资源

# 视频文件
GET    /api/videos/{id}/file        # 下载视频文件
GET    /api/videos/{id}/audio       # 下载音频文件

# 转录资源
POST   /api/transcripts             # 创建转录（支持 video_id 或直接上传）
GET    /api/transcripts/{id}        # 获取转录状态
GET    /api/transcripts/{id}/events # SSE 订阅转录进度

# 大纲资源
POST   /api/transcripts/{id}/outline  # 创建大纲
GET    /api/transcripts/{id}/outline  # 获取大纲
GET    /api/transcripts/{id}/outline/events  # SSE 订阅

# 文章资源
POST   /api/transcripts/{id}/article  # 创建文章
GET    /api/transcripts/{id}/article  # 获取文章
GET    /api/transcripts/{id}/article/events  # SSE 订阅
```

### API 详细规格

#### POST /api/videos
创建视频资源并开始下载（URL 会被规范化去重）

**请求**:
```json
{
  "url": "https://example.com/video?param=xxx"
}
```

**响应** (201 Created) - 新建:
```json
{
  "id": "a1b2c3d4",
  "url": "https://example.com/video",
  "status": "downloading",
  "created": true,
  "created_at": "2025-01-01T00:00:00Z"
}
```

**响应** (200 OK) - 已存在:
```json
{
  "id": "a1b2c3d4",
  "url": "https://example.com/video",
  "status": "completed",
  "created": false,
  "created_at": "2025-01-01T00:00:00Z"
}
```

> `created: false` 表示返回的是已存在的记录，前端可直接使用或订阅 SSE

---

#### GET /api/videos/{id}
获取视频状态（用于断线重连）

**响应** (200 OK):
```json
{
  "id": "a1b2c3d4",
  "url": "https://example.com/video",
  "title": "视频标题",
  "status": "completed",
  "has_video": true,
  "has_audio": true,
  "created_at": "2025-01-01T00:00:00Z"
}
```

---

#### GET /api/videos/{id}/events
SSE 订阅下载进度

**响应** (text/event-stream):
```
event: status
data: {"status": "downloading", "progress": "10%"}

event: status
data: {"status": "downloading", "progress": "50%"}

event: status
data: {"status": "completed", "title": "视频标题"}

event: done
data: {}
```

**错误事件**:
```
event: error
data: {"detail": "下载失败：网络超时"}
```

---

#### DELETE /api/videos/{id}
删除视频及所有派生资源

**响应** (200 OK):
```json
{
  "message": "视频已删除"
}
```

---

#### POST /api/transcripts
创建转录（支持多种输入方式）

**请求方式1** - 关联已下载的视频:
```json
{
  "video_id": "a1b2c3d4"
}
```

**请求方式2** - 直接上传音频（将来扩展）:
```
multipart/form-data
- audio: 音频文件
```

**前置条件**: 如果使用 video_id，则 `video.status == "completed"`

**响应** (201 Created):
```json
{
  "id": "t1r2a3n4",
  "video_id": "a1b2c3d4",
  "status": "processing"
}
```

---

#### GET /api/transcripts/{id}
获取转录状态

**响应** (200 OK):
```json
{
  "id": "t1r2a3n4",
  "video_id": "a1b2c3d4",
  "status": "completed",
  "content": "转录文本内容...",
  "created_at": "2025-01-01T00:01:00Z"
}
```

---

#### GET /api/transcripts/{id}/events
SSE 订阅转录进度

**响应** (text/event-stream):
```
event: status
data: {"status": "processing", "progress": "提取音频中..."}

event: status
data: {"status": "processing", "progress": "转录中..."}

event: status
data: {"status": "completed"}

event: done
data: {}
```

### 错误响应格式

所有失败请求返回统一格式：

```json
{
  "detail": "具体错误信息"
}
```

HTTP 状态码：
- `400` - 请求参数错误
- `404` - 资源不存在
- `409` - 状态冲突（如视频未下载完就请求转录）
- `500` - 服务器内部错误（下载失败、API 调用失败等）

---

#### POST /api/transcripts/{id}/outline
创建大纲

**前置条件**: `transcript.status == "completed"`

**响应** (201 Created):
```json
{
  "id": "o1u2t3l4",
  "transcript_id": "t1r2a3n4",
  "status": "processing"
}
```

---

#### GET /api/transcripts/{id}/outline
获取大纲

**响应** (200 OK):
```json
{
  "id": "o1u2t3l4",
  "transcript_id": "t1r2a3n4",
  "status": "completed",
  "content": "大纲内容...",
  "created_at": "2025-01-01T00:05:00Z"
}
```

---

#### POST /api/transcripts/{id}/article
创建文章

**前置条件**: `transcript.status == "completed"`

**响应** (201 Created):
```json
{
  "id": "a1r2t3i4",
  "transcript_id": "t1r2a3n4",
  "status": "processing"
}
```

---

#### GET /api/transcripts/{id}/article
获取文章

**响应** (200 OK):
```json
{
  "id": "a1r2t3i4",
  "transcript_id": "t1r2a3n4",
  "status": "completed",
  "content": "文章内容...",
  "created_at": "2025-01-01T00:06:00Z"
}
```

---

## 四、用户流程

### 完整流程示例（使用 SSE）

```
用户输入 URL: https://example.com/video
        │
        ▼
POST /api/videos { url: "..." }
        │
        ├─→ 返回 { id: "v123", status: "downloading" }
        │
        ▼
订阅 GET /api/videos/v123/events (SSE)
        │
        ├─→ event: status { progress: "10%" }
        ├─→ event: status { progress: "50%" }
        ├─→ event: status { status: "completed" }
        ├─→ event: done
        │
        ▼
POST /api/transcripts { video_id: "v123" }
        │
        ├─→ 返回 { id: "t456", status: "processing" }
        │
        ▼
订阅 GET /api/transcripts/t456/events (SSE)
        │
        ├─→ event: status { progress: "提取音频中..." }
        ├─→ event: status { progress: "转录中..." }
        ├─→ event: status { status: "completed" }
        ├─→ event: done
        │
        ▼
GET /api/transcripts/t456  →  获取转录内容
        │
        ▼
用户点击"生成大纲"
        │
        ▼
POST /api/transcripts/t456/outline
        │
        ▼
订阅 GET /api/transcripts/t456/outline/events (SSE)
        │
        ├─→ event: status { status: "completed" }
        │
        ▼
GET /api/transcripts/t456/outline  →  获取大纲内容
```

### 资源依赖图

```
┌─────────────────────────────────────────────────────────────────────┐
│                           videos 表                                  │
│                    (可选输入源，video_id 可为空)                      │
├─────────────────────────────────────────────────────────────────────┤
│              pending → downloading → completed                       │
└─────────────────────────────────────────────────────────────────────┘
                                    │
                                    │ 可选关联
                                    ▼
┌─────────────────────────────────────────────────────────────────────┐
│                        transcripts 表                                │
│                         (核心资源)                                   │
├─────────────────────────────────────────────────────────────────────┤
│              pending → processing → completed                        │
└─────────────────────────────────────────────────────────────────────┘
                                    │
                                    │ transcript.status == completed
                    ┌───────────────┴───────────────┐
                    ▼                               ▼
        ┌─────────────────────┐         ┌─────────────────────┐
        │    outlines 表      │         │    articles 表      │
        ├─────────────────────┤         ├─────────────────────┤
        │ pending → processing│         │ pending → processing│
        │        ↘ completed  │         │        ↘ completed  │
        └─────────────────────┘         └─────────────────────┘

> 注：失败时通过 SSE 发送 error 事件，记录不入库，用户可重试
```

---

## 五、实施步骤

### Phase 1: 数据库层

1. 创建 `app/database.py`
   - 定义数据库连接（aiosqlite）
   - 创建表结构
   - 提供 CRUD 操作函数

### Phase 2: API 层重构

1. 重写 `app/web.py`
   - 移除 task 相关代码
   - 实现资源导向端点
   - 实现 SSE 端点
   - 使用数据库替代内存存储

2. 保持服务层不变
   - `video_downloader.py` - 下载逻辑
   - `transcribe.py` - 转录逻辑
   - `gitcode_ai.py` - AI 生成逻辑

### Phase 3: 前端适配

1. 更新 `frontend/src/api/`
   - 实现新的 API 调用
   - 添加 SSE 订阅函数

2. 更新组件
   - 使用 EventSource 订阅 SSE
   - 适配新的数据结构

---

## 六、文件变更清单

| 文件 | 操作 | 说明 |
|------|------|------|
| `app/database.py` | 新建 | SQLite 数据库操作 |
| `app/web.py` | 重写 | 资源导向 API + SSE |
| `data/v2t.db` | 新建 | SQLite 数据库文件 |
| `frontend/src/api/video.js` | 新建 | 视频 API |
| `frontend/src/api/transcript.js` | 新建 | 转录 API + SSE |
| `frontend/src/api/task.js` | 删除 | 移除旧 API |
| `frontend/src/composables/useSSE.js` | 新建 | SSE 订阅 composable |
| `frontend/src/composables/useTaskPolling.js` | 删除 | 移除旧轮询 |
