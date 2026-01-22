"""Pydantic 请求/响应模型"""

from pydantic import BaseModel


class ProcessRequest(BaseModel):
    """视频处理请求"""

    url: str


class StreamRequest(BaseModel):
    """流式生成请求"""

    system_prompt: str = ""
    user_prompt: str = ""


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
    zhihu_system: str
    zhihu_user: str


class VideoTaskResponse(BaseModel):
    """视频任务响应"""

    task_id: str
    status: str
    progress: str
    title: str = ""
    resource_id: str | None = None
    video_url: str | None = None
    audio_url: str | None = None
    transcript: str = ""
    error: str = ""


class OutlineTaskResponse(BaseModel):
    """大纲任务响应"""

    task_id: str
    status: str
    progress: str
    outline: str = ""
    error: str = ""


class ArticleTaskResponse(BaseModel):
    """文章任务响应"""

    task_id: str
    status: str
    progress: str
    article: str = ""
    error: str = ""


class PodcastTaskResponse(BaseModel):
    """播客任务响应"""

    task_id: str
    status: str
    progress: str
    title: str = ""
    podcast_script: str = ""
    has_podcast_audio: bool = False
    podcast_error: str = ""
    error: str = ""


class ZhihuArticleTaskResponse(BaseModel):
    """知乎文章任务响应"""

    task_id: str
    status: str
    progress: str
    zhihu_article: str = ""
    error: str = ""
