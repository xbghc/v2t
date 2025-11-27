"""GitCode AI API 服务 - 使用 OpenAI 兼容模式"""

from openai import AsyncOpenAI

from app.config import get_settings


class GitCodeAIError(Exception):
    """GitCode AI API 错误"""
    pass


def get_client() -> AsyncOpenAI:
    """获取 OpenAI 客户端"""
    settings = get_settings()

    if not settings.gitcode_ai_token:
        raise GitCodeAIError("GITCODE_AI_TOKEN 未配置")

    return AsyncOpenAI(
        base_url=settings.gitcode_ai_base_url,
        api_key=settings.gitcode_ai_token,
    )


async def chat(
    messages: list[dict],
    max_tokens: int = 4096,
    temperature: float = 0.6,
) -> str:
    """
    调用 AI 聊天接口

    Args:
        messages: 消息列表
        max_tokens: 最大 token 数
        temperature: 温度参数

    Returns:
        str: 响应内容
    """
    settings = get_settings()
    client = get_client()

    # GitCode API 需要流式模式
    stream = await client.chat.completions.create(
        model=settings.gitcode_ai_model,
        messages=messages,
        stream=True,
        max_tokens=max_tokens,
        temperature=temperature,
        top_p=0.95,
    )

    result = []
    async for chunk in stream:
        if chunk.choices[0].delta.content:
            result.append(chunk.choices[0].delta.content)

    return "".join(result)


async def translate_subtitle(content: str, target_language: str) -> str:
    """
    翻译字幕内容

    Args:
        content: 字幕内容
        target_language: 目标语言

    Returns:
        str: 翻译后的内容
    """
    messages = [
        {
            "role": "system",
            "content": f"你是一个专业的字幕翻译专家。请将以下字幕内容翻译成{target_language}，保持原有的时间轴格式不变。"
        },
        {
            "role": "user",
            "content": content
        }
    ]

    return await chat(messages)


async def generate_outline(content: str) -> str:
    """
    根据字幕内容生成大纲和时间线

    Args:
        content: 字幕内容

    Returns:
        str: 大纲和时间线
    """
    messages = [
        {
            "role": "system",
            "content": "你是一个内容分析专家。请根据以下字幕内容，整理出视频的大纲和时间线。格式要清晰，包含各部分的时间点和主题。"
        },
        {
            "role": "user",
            "content": content
        }
    ]

    return await chat(messages)


async def generate_article(content: str) -> str:
    """
    将字幕内容转化为完整文章

    Args:
        content: 字幕内容

    Returns:
        str: 完整文章
    """
    messages = [
        {
            "role": "system",
            "content": "你是一个专业的内容编辑。请将以下字幕内容整理成一篇结构清晰、内容完整的文章。保留所有重要信息，使用恰当的段落和标题组织内容。"
        },
        {
            "role": "user",
            "content": content
        }
    ]

    return await chat(messages)
