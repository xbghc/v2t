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
            "content": """你是一个内容分析专家，擅长提取视频的结构化大纲。

## 任务
根据视频转录内容，生成详细的大纲和时间线。

## 要求
1. **提取时间点**：根据转录中的时间戳 [MM:SS] 标注每个章节的起始时间
2. **层级分明**：主题用 ## 标注，子主题用 ### 标注
3. **要点概括**：每个章节下列出 2-5 个核心要点
4. **保留细节**：重要的例子、数据、引用要保留

## 格式示例
```
## [00:00] 开场介绍
- 要点1
- 要点2

## [02:30] 主题一：xxx
### 子主题 1.1
- 要点
- 要点

### 子主题 1.2
- 要点
```"""
        },
        {
            "role": "user",
            "content": f"请为以下视频内容生成详细大纲：\n\n{content}"
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
            "content": """你是一个专业的内容编辑，擅长将视频转录内容转化为高质量文章。

## 任务
将以下视频转录内容整理成一篇详细、完整的文章。

## 要求
1. **保留所有细节**：不要省略或压缩原文中的观点、例子、论据
2. **忠实原意**：保持说话者的原始表达风格和语气
3. **详细展开**：每个观点都要充分展开，包括背景、论述、例证
4. **篇幅要求**：文章长度应与原视频时长相匹配，不要过度精简

## 格式
- 使用二级标题（##）划分主要章节
- 使用三级标题（###）划分子主题
- 重要观点可以用引用格式（>）突出
- 列举要点时使用列表"""
        },
        {
            "role": "user",
            "content": f"请将以下视频转录内容整理成详细文章：\n\n{content}"
        }
    ]

    return await chat(messages, max_tokens=8192)
