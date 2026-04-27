"""Pydantic 请求/响应模型"""

from pydantic import BaseModel

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
    name: str  # video, audio, transcript, outline, article, podcast, zhihu
    resource_type: str  # video | audio | text
    download_url: str | None = None
    content: str | None = None  # text 类型直接返回内容
    created_at: float


class WorkspaceResponse(BaseModel):
    """工作区响应"""

    workspace_id: str
    url: str
    title: str
    status: str  # pending, downloading, transcribing, ready, failed
    progress: str
    error: str
    resources: list[WorkspaceResourceResponse]
    created_at: float
    last_accessed_at: float
    # B 站分 P 系列元数据（非分 P 视频留空字符串 + 0）
    series_bvid: str = ""
    series_index: int = 0


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
    zhihu_system: str
    zhihu_user: str
