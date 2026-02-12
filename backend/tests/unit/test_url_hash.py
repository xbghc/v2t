"""URL 规范化和哈希测试"""

from app.utils.url_hash import compute_url_hash, normalize_url


class TestUrlHash:
    """URL 规范化和哈希测试"""

    def test_normalize_removes_tracking_params(self):
        """移除追踪参数"""
        url = "https://www.bilibili.com/video/BV123?vd_source=abc&utm_source=test"
        normalized = normalize_url(url)
        assert "vd_source" not in normalized
        assert "utm_source" not in normalized

    def test_normalize_preserves_important_params(self):
        """保留重要参数"""
        url = "https://www.bilibili.com/video/BV123?p=2&vd_source=abc"
        normalized = normalize_url(url)
        assert "p=2" in normalized

    def test_normalize_lowercase(self):
        """URL 小写化"""
        url = "HTTPS://WWW.BILIBILI.COM/video/BV123"
        normalized = normalize_url(url)
        assert normalized.startswith("https://www.bilibili.com")

    def test_normalize_removes_trailing_slash(self):
        """移除尾部斜杠"""
        url = "https://www.bilibili.com/video/BV123/"
        normalized = normalize_url(url)
        assert not normalized.endswith("/")

    def test_same_url_same_hash(self):
        """相同 URL 产生相同哈希"""
        url1 = "https://www.bilibili.com/video/BV123?vd_source=abc"
        url2 = "https://www.bilibili.com/video/BV123?vd_source=xyz"
        assert compute_url_hash(url1) == compute_url_hash(url2)

    def test_different_url_different_hash(self):
        """不同 URL 产生不同哈希"""
        url1 = "https://www.bilibili.com/video/BV123"
        url2 = "https://www.bilibili.com/video/BV456"
        assert compute_url_hash(url1) != compute_url_hash(url2)

    def test_different_p_param_different_hash(self):
        """不同分P产生不同哈希"""
        url1 = "https://www.bilibili.com/video/BV123?p=1"
        url2 = "https://www.bilibili.com/video/BV123?p=2"
        assert compute_url_hash(url1) != compute_url_hash(url2)
