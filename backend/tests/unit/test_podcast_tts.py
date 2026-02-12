"""播客 TTS 服务测试"""

import pytest

from app.services.podcast_tts import (
    TTS_MAX_CHARS,
    PodcastTTSError,
    _split_long_segment,
    iter_safe_segments,
    parse_segments,
    tts_char_count,
)


class TestTtsCharCount:
    """测试 tts_char_count 函数"""

    def test_chinese_chars(self):
        """中文字符算 2"""
        assert tts_char_count("你好") == 4
        assert tts_char_count("中文测试") == 8

    def test_english_chars(self):
        """英文字符算 1"""
        assert tts_char_count("hello") == 5
        assert tts_char_count("abc") == 3

    def test_mixed_chars(self):
        """中英混合"""
        assert tts_char_count("你好world") == 4 + 5  # 9
        assert tts_char_count("a中b") == 1 + 2 + 1  # 4

    def test_empty(self):
        """空字符串"""
        assert tts_char_count("") == 0

    def test_punctuation(self):
        """标点符号"""
        assert tts_char_count("。") == 2  # 中文标点
        assert tts_char_count(".") == 1  # 英文标点


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


class TestSplitLongSegment:
    """测试 _split_long_segment 函数"""

    def test_split_short_text(self):
        """短文本不分割"""
        text = "这是短文本。"  # 12 TTS 字符
        result = _split_long_segment(text, TTS_MAX_CHARS)
        assert result == [text]

    def test_split_by_period(self):
        """优先按句号分割"""
        # 每个"句子。"= 6 字符 (4+2)，30 个 = 180 TTS 字符
        text = "句子。" * 30
        result = _split_long_segment(text, 100)
        assert len(result) >= 2
        for segment in result:
            assert tts_char_count(segment) <= 100

    def test_split_by_comma(self):
        """其次按逗号分割"""
        # 没有句号，只有逗号
        text = "部分，" * 30  # 每个 6 TTS 字符
        result = _split_long_segment(text, 100)
        assert len(result) >= 2
        for segment in result:
            assert tts_char_count(segment) <= 100

    def test_split_force_cut(self):
        """无标点时强制截断"""
        # 350 中文字 = 700 TTS 字符，超过 600 限制
        text = "这" * 350
        result = _split_long_segment(text, TTS_MAX_CHARS)
        assert len(result) >= 2
        for segment in result:
            assert tts_char_count(segment) <= TTS_MAX_CHARS
        # 内容完整保留
        assert "".join(result) == text

    def test_split_mixed_punctuation(self):
        """混合标点分割"""
        text = "陈述。疑问？感叹！" * 20  # 每组 18 TTS 字符
        result = _split_long_segment(text, 100)
        assert len(result) >= 2
        for segment in result:
            assert tts_char_count(segment) <= 100

    def test_split_english_text(self):
        """英文文本分割（每字符算 1）"""
        text = "Word. " * 150  # 每个 6 字符，共 900 字符
        result = _split_long_segment(text, TTS_MAX_CHARS)
        assert len(result) >= 2
        for segment in result:
            assert tts_char_count(segment) <= TTS_MAX_CHARS

    def test_split_empty_text(self):
        """空文本返回空列表"""
        assert _split_long_segment("", TTS_MAX_CHARS) == []


class TestIterSafeSegments:
    """测试 iter_safe_segments 函数"""

    def test_short_segments_pass_through(self):
        """短段落直接通过"""
        segments = ["短段落一。", "短段落二。", "短段落三。"]
        result = list(iter_safe_segments(segments))
        assert result == segments

    def test_long_segment_split(self):
        """超长段落自动分割"""
        # 100 个中文句子 = 约 1800 TTS 字符
        long_segment = "这是一个句子。" * 100
        result = list(iter_safe_segments([long_segment]))
        assert len(result) > 1
        for segment in result:
            assert tts_char_count(segment) <= TTS_MAX_CHARS

    def test_mixed_segments(self):
        """混合长短段落"""
        short = "这是短段落。"
        long = "这是一个句子。" * 100  # 超长
        segments = [short, long, short]
        result = list(iter_safe_segments(segments))
        # 短段落保持不变
        assert result[0] == short
        assert result[-1] == short
        # 所有段落不超过限制
        for segment in result:
            assert tts_char_count(segment) <= TTS_MAX_CHARS

    def test_empty_list(self):
        """空列表返回空"""
        assert list(iter_safe_segments([])) == []

    def test_at_limit(self):
        """刚好在限制边界的段落"""
        # 300 中文字 = 600 TTS 字符，刚好等于限制
        segment = "测" * 300
        assert tts_char_count(segment) == TTS_MAX_CHARS
        result = list(iter_safe_segments([segment]))
        assert len(result) == 1
        assert result[0] == segment

    def test_force_cut_fallback(self):
        """无标点超长段落强制截断"""
        # 350 中文字 = 700 TTS 字符，超过限制
        long_segment = "这" * 350
        result = list(iter_safe_segments([long_segment]))
        assert len(result) >= 2
        for segment in result:
            assert tts_char_count(segment) <= TTS_MAX_CHARS
        # 内容完整保留
        assert "".join(result) == long_segment
