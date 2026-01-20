"""LLM API 测试"""

import pytest

from app.services.llm import (
    LLMError,
    chat,
    chat_complete,
    generate_article,
    generate_outline,
)


async def collect_stream(async_gen):
    """收集异步生成器的所有输出"""
    result = []
    async for chunk in async_gen:
        result.append(chunk)
    return "".join(result)


@pytest.mark.asyncio
async def test_chat():
    """测试基本聊天功能（流式）"""
    try:
        messages = [
            {"role": "user", "content": "你好，请用一句话介绍自己"}
        ]
        result = await collect_stream(chat(messages, max_tokens=100))
        print(f"响应: {result}")
        assert result
        assert len(result) > 0
    except LLMError as e:
        pytest.skip(f"跳过测试: {e}")


@pytest.mark.asyncio
async def test_chat_complete():
    """测试基本聊天功能（完整响应）"""
    try:
        messages = [
            {"role": "user", "content": "你好，请用一句话介绍自己"}
        ]
        result = await chat_complete(messages, max_tokens=100)
        print(f"响应: {result}")
        assert result
        assert len(result) > 0
    except LLMError as e:
        pytest.skip(f"跳过测试: {e}")


@pytest.mark.asyncio
async def test_generate_outline():
    """测试大纲生成功能（流式）"""
    try:
        content = """
        00:00:00 大家好，今天我们来讲解Python基础
        00:01:00 首先是变量和数据类型
        00:05:00 然后是条件语句
        00:10:00 最后是循环语句
        00:15:00 感谢收看
        """
        result = await collect_stream(generate_outline(content))
        print(f"大纲:\n{result}")
        assert result
    except LLMError as e:
        pytest.skip(f"跳过测试: {e}")


@pytest.mark.asyncio
async def test_generate_article():
    """测试文章生成功能（流式）"""
    try:
        content = """
        大家好，今天我们来讲解Python基础。
        Python是一门简单易学的编程语言。
        它被广泛用于数据科学、Web开发等领域。
        感谢收看。
        """
        result = await collect_stream(generate_article(content))
        print(f"文章:\n{result}")
        assert result
    except LLMError as e:
        pytest.skip(f"跳过测试: {e}")
