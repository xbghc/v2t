"""Pydantic 请求/响应模型"""

from pydantic import BaseModel, Field

# ===== Workspace 相关 =====


class CreateWorkspaceRequest(BaseModel):
    """创建工作区请求"""

    url: str
    # B 站分 P 系列元数据（前端探测到分 P 后选集时带上）
    series_bvid: str | None = None
    series_index: int | None = None


class CreateFromTranscriptRequest(BaseModel):
    """从已有转录文本直接创建工作区"""

    transcript: str
    title: str = ""
    source_url: str = ""


class WorkspaceResourceResponse(BaseModel):
    """资源响应"""

    resource_id: str
    name: str  # video, audio, transcript, outline, article, podcast
    resource_type: str  # video | audio | text
    download_url: str | None = None
    content: str | None = None  # text 类型直接返回内容
    ready: bool = False
    created_at: float


class GenerationTaskResponse(BaseModel):
    """生成任务响应（GET workspace 时附带 + 启动端点返回）"""

    task_id: str
    workspace_id: str
    content_type: str  # outline / article / podcast
    status: str  # pending / running / done / failed
    resource_id: str = ""
    audio_resource_id: str = ""
    audio_error: str = ""
    error: str = ""
    stream_url: str  # 消费端点 URL，前端直接 SSE 连接，不用拼协议


class WorkspaceResponse(BaseModel):
    """工作区响应"""

    workspace_id: str
    url: str
    title: str
    status: str  # pending, processing, ready, failed
    progress: str
    error: str  # 用户可读的友好消息
    error_kind: str = ""  # video_too_long / download_failed / transcribe_failed / unknown / ""(无错误)
    resources: list[WorkspaceResourceResponse]
    generations: list[GenerationTaskResponse] = []  # 各内容类型当前活跃 task（前端恢复用）
    created_at: float
    last_accessed_at: float
    # B 站分 P 系列元数据（非分 P 视频留空字符串 + 0）
    series_bvid: str = ""
    series_index: int = 0
    # 阶段耗时（秒）。stage_name → duration；audio_duration 为视频本身时长
    timings: dict[str, float] = Field(default_factory=dict)


class TranscriptSegmentMessage(BaseModel):
    """SSE 推送的单段转录增量"""

    start: float
    end: float
    text: str
    chunk_index: int = -1


class WorkspaceLookupResponse(BaseModel):
    """系列分 P → workspace_id 查找响应"""

    workspace_id: str | None = None


# ===== 流式生成相关 =====


class StreamRequest(BaseModel):
    """流式生成请求"""

    system_prompt: str = ""
    user_prompt: str = ""


# ===== 提示词相关 =====


class PromptsResponse(BaseModel):
    """默认提示词响应"""

    outline_system: str
    outline_user: str
    article_system: str
    article_user: str
    podcast_system: str
    podcast_user: str


# ===== 后台管理（运营统计）相关 =====


class PageviewRequest(BaseModel):
    """前端路由切换上报的页面访问埋点"""

    path: str = ""
    visitor_id: str = ""


class DailyPoint(BaseModel):
    """单日 PV/UV 数据点"""

    date: str  # YYYY-MM-DD
    pv: int = 0
    uv: int = 0


class AdminStatsResponse(BaseModel):
    """后台仪表盘汇总统计"""

    pv_total: int = 0
    uv_total: int = 0
    transcribe_total: int = 0
    ready_count: int = 0
    failed_count: int = 0
    success_rate: float = 0.0  # 0~1
    error_kind: dict[str, int] = Field(default_factory=dict)
    daily: list[DailyPoint] = Field(default_factory=list)


class HistoryItem(BaseModel):
    """一条转录历史快照"""

    workspace_id: str
    url: str = ""
    title: str = ""
    status: str = ""
    error_kind: str = ""
    created_at: float = 0.0
    finished_at: float = 0.0
    timings: dict[str, float] = Field(default_factory=dict)


class HistoryListResponse(BaseModel):
    """转录历史分页列表"""

    items: list[HistoryItem] = Field(default_factory=list)
    total: int = 0
    offset: int = 0
    limit: int = 0
