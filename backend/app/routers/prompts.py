"""提示词相关路由"""

from fastapi import APIRouter

from app.models.schemas import PromptsResponse
from app.services.llm import (
    DEFAULT_ARTICLE_SYSTEM_PROMPT,
    DEFAULT_ARTICLE_USER_PROMPT,
    DEFAULT_OUTLINE_SYSTEM_PROMPT,
    DEFAULT_OUTLINE_USER_PROMPT,
    DEFAULT_PODCAST_SYSTEM_PROMPT,
    DEFAULT_PODCAST_USER_PROMPT,
)

router = APIRouter(prefix="/api", tags=["prompts"])


@router.get("/prompts", response_model=PromptsResponse)
async def get_prompts() -> PromptsResponse:
    """获取默认提示词"""
    return PromptsResponse(
        outline_system=DEFAULT_OUTLINE_SYSTEM_PROMPT,
        outline_user=DEFAULT_OUTLINE_USER_PROMPT,
        article_system=DEFAULT_ARTICLE_SYSTEM_PROMPT,
        article_user=DEFAULT_ARTICLE_USER_PROMPT,
        podcast_system=DEFAULT_PODCAST_SYSTEM_PROMPT,
        podcast_user=DEFAULT_PODCAST_USER_PROMPT,
    )
