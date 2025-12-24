# REST API 原子性改进计划

## 一、问题分析总结

### 当前 API 端点

| 端点 | 原子性 | 问题 |
|------|--------|------|
| `POST /api/process` | ❌ 非原子 | 单一端点执行5个串联操作（下载→提取→转录→大纲→文章） |
| `GET /api/task/{task_id}` | ⚠️ 部分 | 返回数据可能与磁盘状态不一致 |
| `GET /api/task/{task_id}/video` | ✅ 原子 | - |
| `GET /api/task/{task_id}/audio` | ✅ 原子 | - |

### 核心问题

1. **单一端点做太多事**: `POST /api/process` 包含下载、提取、转录、生成大纲、生成文章5个步骤
2. **AI生成失败静默忽略**: 大纲和文章生成失败时不报告错误（`web.py:173-183`）
3. **状态值错误**: `download_only` 模式使用 `TRANSCRIBING` 状态表示音频提取（`web.py:133`）
4. **无法重试单个步骤**: 用户只能重新提交整个任务
5. **无法取消任务**: 没有取消机制
6. **内存存储不可靠**: 服务重启丢失所有任务

---

## 二、改进方案

### 新的 API 设计

#### 核心理念
- **每个操作一个端点**: 下载、转录、生成大纲、生成文章分别独立
- **显式状态转换**: 用户决定何时执行下一步
- **支持重试**: 每个步骤可独立重试
- **清晰的错误报告**: 失败原因明确返回

#### 新端点设计

```
# 任务管理
POST   /api/tasks                      # 创建任务（仅创建，不执行）
GET    /api/tasks/{task_id}            # 获取任务状态
DELETE /api/tasks/{task_id}            # 取消/删除任务

# 原子操作
POST   /api/tasks/{task_id}/download   # 下载视频
POST   /api/tasks/{task_id}/transcribe # 转录音频（自动提取音频）
POST   /api/tasks/{task_id}/outline    # 生成大纲
POST   /api/tasks/{task_id}/article    # 生成文章

# 文件下载
GET    /api/tasks/{task_id}/video      # 下载视频文件
GET    /api/tasks/{task_id}/audio      # 下载音频文件

# 便捷端点（可选，保持向后兼容）
POST   /api/process                    # 一键处理（内部调用上述原子操作）
```

#### 状态机设计

```
                                    ┌─────────────┐
                                    │   CREATED   │
                                    └──────┬──────┘
                                           │ POST /download
                                           ▼
                              ┌───────────────────────┐
                              │     DOWNLOADING       │
                              └───────────┬───────────┘
                                          │
                    ┌─────────────────────┴─────────────────────┐
                    ▼                                           ▼
           ┌───────────────┐                           ┌───────────────┐
           │  DOWNLOADED   │                           │    FAILED     │
           └───────┬───────┘                           └───────────────┘
                   │ POST /transcribe                          ▲
                   ▼                                           │
          ┌────────────────┐                                   │
          │  TRANSCRIBING  │───────────────────────────────────┤
          └───────┬────────┘                                   │
                  │                                            │
                  ▼                                            │
          ┌────────────────┐                                   │
          │  TRANSCRIBED   │                                   │
          └───────┬────────┘                                   │
                  │                                            │
     ┌────────────┴────────────┐                               │
     │                         │                               │
     ▼                         ▼                               │
POST /outline            POST /article                         │
     │                         │                               │
     ▼                         ▼                               │
┌──────────┐             ┌──────────┐                          │
│ OUTLINED │             │ ARTICLED │──────────────────────────┘
└──────────┘             └──────────┘
```

---

## 三、实施步骤

### Phase 1: 核心重构 (P0)

#### Step 1.1: 添加新的状态枚举
**文件**: `app/web.py`

```python
class TaskStatus(str, Enum):
    CREATED = "created"           # 新增：任务已创建
    DOWNLOADING = "downloading"
    DOWNLOADED = "downloaded"     # 新增：下载完成
    EXTRACTING = "extracting"     # 新增：提取音频中
    TRANSCRIBING = "transcribing"
    TRANSCRIBED = "transcribed"   # 新增：转录完成
    GENERATING_OUTLINE = "generating_outline"  # 新增
    GENERATING_ARTICLE = "generating_article"  # 新增
    COMPLETED = "completed"
    FAILED = "failed"
```

#### Step 1.2: 扩展 TaskResult 模型
**文件**: `app/web.py`

```python
class TaskResult:
    # 现有字段...

    # 新增字段
    outline_status: str = "pending"    # pending|generating|completed|failed
    outline_error: str | None = None
    article_status: str = "pending"    # pending|generating|completed|failed
    article_error: str | None = None

    # 步骤时间戳
    download_started_at: datetime | None = None
    download_completed_at: datetime | None = None
    transcribe_started_at: datetime | None = None
    transcribe_completed_at: datetime | None = None
```

#### Step 1.3: 创建原子操作端点
**文件**: `app/web.py`

- 实现 `POST /api/tasks` - 仅创建任务，返回 task_id
- 实现 `POST /api/tasks/{task_id}/download` - 仅下载视频
- 实现 `POST /api/tasks/{task_id}/transcribe` - 转录（含提取音频）
- 实现 `POST /api/tasks/{task_id}/outline` - 生成大纲
- 实现 `POST /api/tasks/{task_id}/article` - 生成文章
- 实现 `DELETE /api/tasks/{task_id}` - 取消任务

#### Step 1.4: 修改现有 /api/process 为编排端点
保持向后兼容，内部调用新的原子操作

---

### Phase 2: 错误处理改进 (P1)

#### Step 2.1: 移除静默失败
**文件**: `app/web.py:169-183`

```python
# 改前
try:
    outline = await generate_outline(transcript)
except GitCodeAIError:
    task.outline = ""  # 静默失败

# 改后
try:
    outline = await generate_outline(transcript)
    task.outline_status = "completed"
except GitCodeAIError as e:
    task.outline_status = "failed"
    task.outline_error = str(e)
```

#### Step 2.2: 添加详细错误信息
在 TaskResult 中记录每个步骤的错误详情

---

### Phase 3: 前端适配 (P2)

#### Step 3.1: 更新 API 客户端
**文件**: `frontend/src/api/task.js`

```javascript
// 新增原子操作 API
export const createTask = (url) =>
  axios.post('/api/tasks', { url })

export const downloadVideo = (taskId) =>
  axios.post(`/api/tasks/${taskId}/download`)

export const transcribeAudio = (taskId) =>
  axios.post(`/api/tasks/${taskId}/transcribe`)

export const generateOutline = (taskId) =>
  axios.post(`/api/tasks/${taskId}/outline`)

export const generateArticle = (taskId) =>
  axios.post(`/api/tasks/${taskId}/article`)
```

#### Step 3.2: 更新轮询逻辑
**文件**: `frontend/src/composables/useTaskPolling.js`

适配新的状态枚举和子状态

---

## 四、API 详细规格

### POST /api/tasks
创建新任务（不执行任何操作）

**请求**:
```json
{
  "url": "https://example.com/video"
}
```

**响应** (201 Created):
```json
{
  "task_id": "a1b2c3d4",
  "status": "created",
  "url": "https://example.com/video",
  "created_at": "2025-01-01T00:00:00Z"
}
```

---

### POST /api/tasks/{task_id}/download
下载视频

**前置条件**: `status == "created"`

**响应** (202 Accepted):
```json
{
  "task_id": "a1b2c3d4",
  "status": "downloading",
  "message": "开始下载视频"
}
```

**完成后状态**: `downloaded` 或 `failed`

---

### POST /api/tasks/{task_id}/transcribe
转录音频（自动提取音频）

**前置条件**: `status == "downloaded"`

**响应** (202 Accepted):
```json
{
  "task_id": "a1b2c3d4",
  "status": "extracting",
  "message": "开始提取音频"
}
```

**完成后状态**: `transcribed` 或 `failed`

---

### POST /api/tasks/{task_id}/outline
生成大纲

**前置条件**: `status in ["transcribed", "completed"]`

**响应** (202 Accepted):
```json
{
  "task_id": "a1b2c3d4",
  "outline_status": "generating",
  "message": "开始生成大纲"
}
```

**完成后**: `outline_status = "completed"` 或 `"failed"`

---

### POST /api/tasks/{task_id}/article
生成文章

**前置条件**: `status in ["transcribed", "completed"]`

**响应** (202 Accepted):
```json
{
  "task_id": "a1b2c3d4",
  "article_status": "generating",
  "message": "开始生成文章"
}
```

**完成后**: `article_status = "completed"` 或 `"failed"`

---

### DELETE /api/tasks/{task_id}
取消/删除任务

**响应** (200 OK):
```json
{
  "task_id": "a1b2c3d4",
  "message": "任务已取消"
}
```

---

### GET /api/tasks/{task_id}
获取任务完整状态

**响应** (200 OK):
```json
{
  "task_id": "a1b2c3d4",
  "status": "transcribed",
  "url": "https://example.com/video",
  "title": "视频标题",
  "progress": "转录完成",

  "has_video": true,
  "has_audio": true,

  "transcript": "转录文本...",

  "outline_status": "completed",
  "outline": "大纲内容...",
  "outline_error": null,

  "article_status": "pending",
  "article": null,
  "article_error": null,

  "error": null,

  "created_at": "2025-01-01T00:00:00Z",
  "download_completed_at": "2025-01-01T00:01:00Z",
  "transcribe_completed_at": "2025-01-01T00:05:00Z"
}
```

---

## 五、向后兼容

### 保留 POST /api/process

作为"便捷端点"，内部编排调用原子操作：

```python
@app.post("/api/process")
async def process_video(request: ProcessRequest, background_tasks: BackgroundTasks):
    # 1. 创建任务
    task = create_task(request.url)

    # 2. 启动后台编排
    background_tasks.add_task(orchestrate_full_process, task.task_id, request.download_only)

    return {"task_id": task.task_id, "status": "pending"}

async def orchestrate_full_process(task_id: str, download_only: bool):
    # 按顺序调用原子操作
    await execute_download(task_id)
    await execute_transcribe(task_id)
    if not download_only:
        await execute_outline(task_id)
        await execute_article(task_id)
```

---

## 六、测试计划

1. **单元测试**: 每个原子操作的成功/失败路径
2. **集成测试**: 完整流程编排
3. **并发测试**: 多个任务同时执行
4. **错误恢复测试**: 步骤失败后重试

---

## 七、文件变更清单

| 文件 | 变更类型 | 说明 |
|------|----------|------|
| `app/web.py` | 重构 | 添加新端点，重构状态管理 |
| `frontend/src/api/task.js` | 扩展 | 添加新 API 调用 |
| `frontend/src/composables/useTaskPolling.js` | 修改 | 适配新状态 |
| `frontend/src/components/TaskProgress.vue` | 修改 | 显示细粒度状态 |
