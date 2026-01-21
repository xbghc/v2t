"""Pydantic 请求/响应模型"""

from pydantic import BaseModel


class ProcessRequest(BaseModel):
    """视频处理请求"""

    url: str
    # 生成选项（替代 download_only）
    generate_outline: bool = True
    generate_article: bool = True
    generate_podcast: bool = False
    # 自定义提示词，空字符串表示使用默认
    outline_system_prompt: str = ""
    outline_user_prompt: str = ""
    article_system_prompt: str = ""
    article_user_prompt: str = ""
    podcast_system_prompt: str = ""
    podcast_user_prompt: str = ""


class TextToPodcastRequest(BaseModel):
    """文本转播客请求"""

    text: str
    title: str = ""
    podcast_system_prompt: str = ""
    podcast_user_prompt: str = ""


class PromptsResponse(BaseModel):
    """默认提示词响应"""

    outline_system: str
    outline_user: str
    article_system: str
    article_user: str
    podcast_system: str
    podcast_user: str


class TaskResponse(BaseModel):
    """任务响应"""

    task_id: str
    status: str
    progress: str
    title: str = ""
    resource_id: str | None = None
    video_url: str | None = None  # 视频下载路径
    audio_url: str | None = None  # 音频下载路径
    transcript: str = ""
    outline: str = ""
    article: str = ""
    podcast_script: str = ""
    has_podcast_audio: bool = False
    podcast_error: str = ""  # 播客生成失败的错误信息
    error: str = ""
