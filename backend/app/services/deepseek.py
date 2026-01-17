"""DeepSeek API 服务 - 使用 OpenAI 兼容模式"""

from openai import AsyncOpenAI

from app.config import get_settings


class DeepSeekError(Exception):
    """DeepSeek API 错误"""
    pass


# 默认提示词常量
DEFAULT_OUTLINE_SYSTEM_PROMPT = """你是一个内容分析专家，擅长提取视频的结构化大纲。

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

DEFAULT_OUTLINE_USER_PROMPT = "请为以下视频内容生成详细大纲：\n\n{content}"

DEFAULT_ARTICLE_SYSTEM_PROMPT = """你是一个专业的内容编辑，擅长将视频转录内容转化为高质量文章。

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

DEFAULT_ARTICLE_USER_PROMPT = "请将以下视频转录内容整理成详细文章：\n\n{content}"

DEFAULT_PODCAST_SYSTEM_PROMPT = """你是一位专业的播客脚本作家，擅长将视频内容转换为适合朗读的播客脚本。

## 任务
将视频转录内容改写为播客逐字稿，适合 TTS 语音合成朗读。

## 要求
1. **口语化表达**：使用自然、流畅的口语风格，避免书面语
2. **删除视觉引用**：移除"如图所示"、"看这里"、"屏幕上显示"等视觉相关表述
3. **添加过渡语**：在段落之间加入自然的过渡，如"接下来"、"说到这里"、"值得一提的是"
4. **适合朗读**：避免复杂的长句，保持句子简洁明了
5. **保留核心内容**：确保原视频的关键信息和观点都被保留
6. **去除时间戳**：移除所有 [MM:SS] 格式的时间标记

## 输出格式（严格遵守，必须返回 json）
你必须返回一个有效的 json 对象，格式如下：
{"segments": ["第一段内容...", "第二段内容...", "第三段内容..."]}

## 分段规则（必须严格遵守）
- 每段字数必须控制在 100-300 字之间，绝对不能超过 300 字
- 如果一个语义单元超过 300 字，必须在合适的句号处拆分成多段
- 每段应该是完整的句子，不要在句子中间断开
- 只输出 json，不要有任何其他内容"""

DEFAULT_PODCAST_USER_PROMPT = "请将以下视频转录内容改写为播客脚本，返回 json 格式：\n\n{content}"


def get_client() -> AsyncOpenAI:
    """获取 OpenAI 兼容客户端"""
    settings = get_settings()

    if not settings.deepseek_api_key:
        raise DeepSeekError("DEEPSEEK_API_KEY 未配置")

    return AsyncOpenAI(
        base_url=settings.deepseek_base_url,
        api_key=settings.deepseek_api_key,
    )


async def chat(
    messages: list[dict],
    max_tokens: int = 4096,
    temperature: float = 0.6,
    response_format: dict | None = None,
) -> str:
    """
    调用 AI 聊天接口

    Args:
        messages: 消息列表
        max_tokens: 最大 token 数
        temperature: 温度参数
        response_format: 响应格式，如 {"type": "json_object"}

    Returns:
        str: 响应内容
    """
    settings = get_settings()
    client = get_client()

    # 构建请求参数
    kwargs = {
        "model": settings.deepseek_model,
        "messages": messages,
        "stream": True,
        "max_tokens": max_tokens,
        "temperature": temperature,
    }
    if response_format:
        kwargs["response_format"] = response_format

    stream = await client.chat.completions.create(**kwargs)

    result = []
    async for chunk in stream:
        if chunk.choices[0].delta.content:
            result.append(chunk.choices[0].delta.content)

    return "".join(result)


async def generate_outline(
    content: str,
    system_prompt: str | None = None,
    user_prompt: str | None = None,
) -> str:
    """
    根据字幕内容生成大纲和时间线

    Args:
        content: 字幕内容
        system_prompt: 自定义系统提示词，为空则使用默认
        user_prompt: 自定义用户提示词，为空则使用默认，使用 {content} 占位符

    Returns:
        str: 大纲和时间线
    """
    messages = [
        {
            "role": "system",
            "content": system_prompt or DEFAULT_OUTLINE_SYSTEM_PROMPT,
        },
        {
            "role": "user",
            "content": (user_prompt or DEFAULT_OUTLINE_USER_PROMPT).format(content=content),
        },
    ]

    return await chat(messages)


async def generate_article(
    content: str,
    system_prompt: str | None = None,
    user_prompt: str | None = None,
) -> str:
    """
    将字幕内容转化为完整文章

    Args:
        content: 字幕内容
        system_prompt: 自定义系统提示词，为空则使用默认
        user_prompt: 自定义用户提示词，为空则使用默认，使用 {content} 占位符

    Returns:
        str: 完整文章
    """
    messages = [
        {
            "role": "system",
            "content": system_prompt or DEFAULT_ARTICLE_SYSTEM_PROMPT,
        },
        {
            "role": "user",
            "content": (user_prompt or DEFAULT_ARTICLE_USER_PROMPT).format(content=content),
        },
    ]

    return await chat(messages, max_tokens=8192)


async def generate_podcast_script(
    content: str,
    system_prompt: str | None = None,
    user_prompt: str | None = None,
) -> str:
    """
    将转录内容转换为播客脚本

    Args:
        content: 转录内容
        system_prompt: 自定义系统提示词，为空则使用默认
        user_prompt: 自定义用户提示词，为空则使用默认，使用 {content} 占位符

    Returns:
        str: 播客脚本（JSON 格式）
    """
    messages = [
        {
            "role": "system",
            "content": system_prompt or DEFAULT_PODCAST_SYSTEM_PROMPT,
        },
        {
            "role": "user",
            "content": (user_prompt or DEFAULT_PODCAST_USER_PROMPT).format(content=content),
        },
    ]

    return await chat(
        messages,
        max_tokens=8192,
        response_format={"type": "json_object"},
    )
