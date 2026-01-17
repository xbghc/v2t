"""播客 TTS 服务测试"""

import pytest

from app.services.podcast_tts import (
    TTS_MAX_CHARS,
    PodcastTTSError,
    parse_segments,
    split_by_sentence,
    validate_and_fix_segments,
)


class TestParseSegments:
    """测试 parse_segments 函数"""

    def test_parse_segments_json_basic(self):
        """基本 JSON 格式解析"""
        script = '{"segments": ["第一段内容。", "第二段内容。", "第三段内容。"]}'
        result = parse_segments(script)
        assert len(result) == 3
        assert result[0] == "第一段内容。"
        assert result[1] == "第二段内容。"
        assert result[2] == "第三段内容。"

    def test_parse_segments_json_markdown(self):
        """Markdown 代码块中的 JSON"""
        script = '```json\n{"segments": ["第一段", "第二段"]}\n```'
        result = parse_segments(script)
        assert len(result) == 2
        assert result[0] == "第一段"
        assert result[1] == "第二段"

    def test_parse_segments_empty(self):
        """空脚本抛出异常"""
        with pytest.raises(PodcastTTSError):
            parse_segments("")
        with pytest.raises(PodcastTTSError):
            parse_segments("   ")

    def test_parse_segments_invalid_json(self):
        """非 JSON 格式抛出异常"""
        with pytest.raises(PodcastTTSError) as exc_info:
            parse_segments("这是一段没有分隔符的内容。")
        assert "无法解析播客脚本 JSON 格式" in str(exc_info.value)

    def test_parse_segments_whitespace(self):
        """去除段落多余空白"""
        script = '{"segments": ["  第一段  ", "  第二段  "]}'
        result = parse_segments(script)
        assert len(result) == 2
        assert result[0] == "第一段"
        assert result[1] == "第二段"

    def test_parse_segments_filter_empty(self):
        """过滤空段落"""
        script = '{"segments": ["第一段", "", "第二段", "   "]}'
        result = parse_segments(script)
        assert len(result) == 2
        assert result[0] == "第一段"
        assert result[1] == "第二段"


class TestSplitBySentence:
    """测试 split_by_sentence 函数"""

    def test_split_by_sentence_period(self):
        """按句号分割"""
        text = "第一句话。第二句话。第三句话。"
        result = split_by_sentence(text)
        assert len(result) >= 1
        # 内容应该完整保留
        assert "".join(result) == text

    def test_split_by_sentence_mixed(self):
        """混合标点分割"""
        text = "这是陈述句。这是疑问句？这是感叹句！"
        result = split_by_sentence(text)
        assert len(result) >= 1
        assert "".join(result) == text

    def test_split_by_sentence_empty(self):
        """空文本返回空列表"""
        assert split_by_sentence("") == []
        assert split_by_sentence("   ") == []

    def test_split_by_sentence_english(self):
        """英文标点分割"""
        text = "First sentence. Second sentence! Third sentence?"
        result = split_by_sentence(text)
        assert len(result) >= 1
        assert "".join(result) == text

    def test_split_by_sentence_long_text(self):
        """长文本分割不超过限制"""
        # 创建超长文本
        text = "这是一个测试句子。" * 100  # 约 900 字符
        result = split_by_sentence(text)
        for segment in result:
            assert len(segment) <= TTS_MAX_CHARS


class TestValidateAndFixSegments:
    """测试 validate_and_fix_segments 函数"""

    def test_validate_segments_all_valid(self):
        """所有段落合规"""
        segments = ["短段落一。", "短段落二。", "短段落三。"]
        result = validate_and_fix_segments(segments)
        assert result == segments

    def test_validate_segments_warning_fallback(self):
        """超长段落触发警告和 fallback"""
        # 创建一个超长段落，但可以按句号分割
        long_segment = "这是一个句子。" * 100  # 约 900 字符
        segments = [long_segment]
        result = validate_and_fix_segments(segments)
        # 应该被分割成多段
        assert len(result) > 1
        # 每段不超过限制
        for segment in result:
            assert len(segment) <= TTS_MAX_CHARS

    def test_validate_segments_fallback_success(self):
        """fallback 成功分割"""
        # 构造一个刚好超过限制但可分割的段落
        long_segment = "第一句话很长很长。" * 50 + "第二句话也很长。" * 50
        segments = [long_segment]
        result = validate_and_fix_segments(segments)
        assert len(result) >= 1
        for segment in result:
            assert len(segment) <= TTS_MAX_CHARS

    def test_validate_segments_fallback_fail(self):
        """fallback 后仍超长抛异常"""
        # 创建一个超长且无标点的段落
        long_segment = "这" * 700  # 700 字符，无标点
        segments = [long_segment]
        with pytest.raises(PodcastTTSError) as exc_info:
            validate_and_fix_segments(segments)
        assert "段落过长且无法分割" in str(exc_info.value)

    def test_validate_segments_mixed(self):
        """混合长短段落"""
        short = "这是短段落。"
        long = "这是一个句子。" * 100  # 超长，可分割
        segments = [short, long, short]
        result = validate_and_fix_segments(segments)
        # 短段落保持不变，长段落被分割
        assert result[0] == short
        assert result[-1] == short
        for segment in result:
            assert len(segment) <= TTS_MAX_CHARS

    def test_validate_segments_empty(self):
        """空列表返回空列表"""
        assert validate_and_fix_segments([]) == []

    def test_validate_segments_at_limit(self):
        """刚好在限制边界的段落"""
        segment = "测" * TTS_MAX_CHARS  # 刚好 600 字符
        result = validate_and_fix_segments([segment])
        assert len(result) == 1
        assert result[0] == segment
