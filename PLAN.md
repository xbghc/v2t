# REST API 原子性改进计划

## 一、设计理念

### 从 Task 到 Resource

| 原设计 | 新设计 |
|--------|--------|
| `task_id` 管理一切 | `video_id` 是核心资源 |
| 一次性启动全流程 | 用户决定每一步 |
| 内存存储 | SQLite 持久化 |
| 轮询 task 状态 | 轮询具体资源状态 |

### 核心原则

1. **资源导向**: 视频是核心资源，转录/大纲/文章是派生资源
2. **原子操作**: 每个 API 只做一件事
3. **持久化**: 使用 SQLite 存储，服务重启不丢失数据
4. **可重试**: 每个步骤可独立重试

---

## 二、数据库设计 (SQLite)

### 表结构

```sql
-- 视频资源（核心）
CREATE TABLE videos (
    id TEXT PRIMARY KEY,              -- 8位UUID
    url TEXT NOT NULL,                -- 原始视频URL
    title TEXT,                       -- 视频标题
    status TEXT DEFAULT 'pending',    -- pending|downloading|completed|failed
    video_path TEXT,                  -- 视频文件路径
    audio_path TEXT,                  -- 音频文件路径
    error TEXT,                       -- 错误信息
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 转录资源
CREATE TABLE transcripts (
    id TEXT PRIMARY KEY,
    video_id TEXT NOT NULL REFERENCES videos(id) ON DELETE CASCADE,
    status TEXT DEFAULT 'pending',    -- pending|processing|completed|failed
    content TEXT,                     -- 转录内容
    error TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 大纲资源
CREATE TABLE outlines (
    id TEXT PRIMARY KEY,
    video_id TEXT NOT NULL REFERENCES videos(id) ON DELETE CASCADE,
    status TEXT DEFAULT 'pending',    -- pending|processing|completed|failed
    content TEXT,
    error TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 文章资源
CREATE TABLE articles (
    id TEXT PRIMARY KEY,
    video_id TEXT NOT NULL REFERENCES videos(id) ON DELETE CASCADE,
    status TEXT DEFAULT 'pending',    -- pending|processing|completed|failed
    content TEXT,
    error TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 索引
CREATE INDEX idx_transcripts_video_id ON transcripts(video_id);
CREATE INDEX idx_outlines_video_id ON outlines(video_id);
CREATE INDEX idx_articles_video_id ON articles(video_id);
```

### 状态枚举

| 状态 | 说明 |
|------|------|
| `pending` | 等待处理 |
| `downloading` | 下载中（仅 videos） |
| `processing` | 处理中 |
| `completed` | 完成 |
| `failed` | 失败 |

---

## 三、API 设计

### 端点概览

```
# 视频资源
POST   /api/videos                  # 创建视频（开始下载）
GET    /api/videos/{id}             # 获取视频状态
DELETE /api/videos/{id}             # 删除视频及所有派生资源

# 视频文件
GET    /api/videos/{id}/file        # 下载视频文件
GET    /api/videos/{id}/audio       # 下载音频文件

# 转录资源
POST   /api/videos/{id}/transcript  # 创建转录（开始处理）
GET    /api/videos/{id}/transcript  # 获取转录结果

# 大纲资源
POST   /api/videos/{id}/outline     # 创建大纲
GET    /api/videos/{id}/outline     # 获取大纲

# 文章资源
POST   /api/videos/{id}/article     # 创建文章
GET    /api/videos/{id}/article     # 获取文章
```

### API 详细规格

#### POST /api/videos
创建视频资源并开始下载

**请求**:
```json
{
  "url": "https://example.com/video"
}
```

**响应** (201 Created):
```json
{
  "id": "a1b2c3d4",
  "url": "https://example.com/video",
  "status": "downloading",
  "created_at": "2025-01-01T00:00:00Z"
}
```

---

#### GET /api/videos/{id}
获取视频完整状态

**响应** (200 OK):
```json
{
  "id": "a1b2c3d4",
  "url": "https://example.com/video",
  "title": "视频标题",
  "status": "completed",
  "has_video": true,
  "has_audio": true,
  "error": null,
  "created_at": "2025-01-01T00:00:00Z",
  "updated_at": "2025-01-01T00:01:00Z"
}
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

#### POST /api/videos/{id}/transcript
创建转录（自动提取音频）

**前置条件**: `video.status == "completed"`

**响应** (201 Created):
```json
{
  "id": "t1r2a3n4",
  "video_id": "a1b2c3d4",
  "status": "processing"
}
```

---

#### GET /api/videos/{id}/transcript
获取转录结果

**响应** (200 OK):
```json
{
  "id": "t1r2a3n4",
  "video_id": "a1b2c3d4",
  "status": "completed",
  "content": "转录文本内容...",
  "error": null,
  "created_at": "2025-01-01T00:01:00Z"
}
```

**响应** (404 Not Found) - 如果未创建转录:
```json
{
  "error": "转录不存在，请先调用 POST /api/videos/{id}/transcript"
}
```

---

#### POST /api/videos/{id}/outline
创建大纲

**前置条件**: 转录已完成 (`transcript.status == "completed"`)

**响应** (201 Created):
```json
{
  "id": "o1u2t3l4",
  "video_id": "a1b2c3d4",
  "status": "processing"
}
```

---

#### POST /api/videos/{id}/article
创建文章

**前置条件**: 转录已完成 (`transcript.status == "completed"`)

**响应** (201 Created):
```json
{
  "id": "a1r2t3i4",
  "video_id": "a1b2c3d4",
  "status": "processing"
}
```

---

## 四、用户流程

### 完整流程示例

```
用户输入 URL: https://example.com/video
        │
        ▼
POST /api/videos { url: "..." }
        │
        ├─→ 返回 { id: "abc123", status: "downloading" }
        │
        ▼
轮询 GET /api/videos/abc123
        │
        ├─→ status: "downloading" → 继续轮询
        ├─→ status: "completed"   → 下载完成
        │
        ▼
POST /api/videos/abc123/transcript
        │
        ├─→ 返回 { status: "processing" }
        │
        ▼
轮询 GET /api/videos/abc123/transcript
        │
        ├─→ status: "processing" → 继续轮询
        ├─→ status: "completed"  → 转录完成，显示内容
        │
        ▼
用户点击"生成大纲"
        │
        ▼
POST /api/videos/abc123/outline
        │
        ▼
轮询 GET /api/videos/abc123/outline
        │
        ├─→ status: "completed" → 显示大纲
```

### 状态流转图

```
                    ┌──────────────────────────────────────────┐
                    │              videos 表                    │
                    ├──────────────────────────────────────────┤
                    │  pending → downloading → completed       │
                    │                      ↘ failed            │
                    └──────────────────────────────────────────┘
                                        │
                                        │ video.status == completed
                                        ▼
┌─────────────────────┐  ┌─────────────────────┐  ┌─────────────────────┐
│   transcripts 表    │  │    outlines 表      │  │    articles 表      │
├─────────────────────┤  ├─────────────────────┤  ├─────────────────────┤
│ pending → processing│  │ pending → processing│  │ pending → processing│
│        ↘ completed  │  │        ↘ completed  │  │        ↘ completed  │
│        ↘ failed     │  │        ↘ failed     │  │        ↘ failed     │
└─────────────────────┘  └─────────────────────┘  └─────────────────────┘
         │                        ▲                        ▲
         │                        │                        │
         └────────────────────────┴────────────────────────┘
                  需要 transcript.status == completed
```

---

## 五、实施步骤

### Phase 1: 数据库层

1. 创建 `app/database.py`
   - 定义数据库连接
   - 创建表结构
   - 提供 CRUD 操作函数

2. 创建数据模型
   - Video, Transcript, Outline, Article 模型类

### Phase 2: API 层重构

1. 重写 `app/web.py`
   - 移除 task 相关代码
   - 实现新的资源导向端点
   - 使用数据库替代内存存储

2. 保持服务层不变
   - `video_downloader.py` - 下载逻辑
   - `transcribe.py` - 转录逻辑
   - `gitcode_ai.py` - AI 生成逻辑

### Phase 3: 前端适配

1. 更新 `frontend/src/api/`
   - 重命名 `task.js` → `video.js`
   - 实现新的 API 调用

2. 更新组件
   - 适配新的数据结构
   - 更新轮询逻辑

---

## 六、文件变更清单

| 文件 | 操作 | 说明 |
|------|------|------|
| `app/database.py` | 新建 | SQLite 数据库操作 |
| `app/models.py` | 新建 | 数据模型定义 |
| `app/web.py` | 重写 | 资源导向 API |
| `data/v2t.db` | 新建 | SQLite 数据库文件 |
| `frontend/src/api/video.js` | 新建 | 视频资源 API |
| `frontend/src/api/task.js` | 删除 | 移除旧 API |
| `frontend/src/composables/useVideoPolling.js` | 新建 | 视频轮询 |
| `frontend/src/composables/useTaskPolling.js` | 删除 | 移除旧轮询 |
