"""GitCode AI API 测试"""

import pytest
from app.services.gitcode_ai import (
    chat,
    translate_subtitle,
    generate_outline,
    generate_article,
    GitCodeAIError,
)


@pytest.mark.asyncio
async def test_chat():
    """测试基本聊天功能"""
    try:
        messages = [
            {"role": "user", "content": "你好，请用一句话介绍自己"}
        ]
        result = await chat(messages, max_tokens=100)
        print(f"响应: {result}")
        assert result
        assert len(result) > 0
    except GitCodeAIError as e:
        pytest.skip(f"跳过测试: {e}")


@pytest.mark.asyncio
async def test_chat_stream():
    """测试流式聊天功能"""
    try:
        messages = [
            {"role": "user", "content": "数到5"}
        ]
        result = await chat(messages, stream=True, max_tokens=100)

        content = ""
        async for chunk in result:
            content += chunk
            print(chunk, end="", flush=True)

        print()
        assert content
    except GitCodeAIError as e:
        pytest.skip(f"跳过测试: {e}")


@pytest.mark.asyncio
async def test_translate_subtitle():
    """测试字幕翻译功能"""
    try:
        srt_content = """1
00:00:01,000 --> 00:00:03,000
Hello, world!

2
00:00:04,000 --> 00:00:06,000
This is a test.
"""
        result = await translate_subtitle(srt_content, "中文")
        print(f"翻译结果:\n{result}")
        assert result
    except GitCodeAIError as e:
        pytest.skip(f"跳过测试: {e}")


@pytest.mark.asyncio
async def test_generate_outline():
    """测试大纲生成功能"""
    try:
        content = """
        00:00:00 大家好，今天我们来讲解Python基础
        00:01:00 首先是变量和数据类型
        00:05:00 然后是条件语句
        00:10:00 最后是循环语句
        00:15:00 感谢收看
        """
        result = await generate_outline(content)
        print(f"大纲:\n{result}")
        assert result
    except GitCodeAIError as e:
        pytest.skip(f"跳过测试: {e}")


@pytest.mark.asyncio
async def test_generate_article():
    """测试文章生成功能"""
    try:
        content = """
        大家好，今天我们来讲解Python基础。
        Python是一门简单易学的编程语言。
        它被广泛用于数据科学、Web开发等领域。
        感谢收看。
        """
        result = await generate_article(content)
        print(f"文章:\n{result}")
        assert result
    except GitCodeAIError as e:
        pytest.skip(f"跳过测试: {e}")
