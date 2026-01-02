"""SQLite 数据库操作层"""

import aiosqlite
import secrets
from pathlib import Path
from urllib.parse import urlparse
from dataclasses import dataclass
from typing import Optional, Any, Type, TypeVar, List

from app.config import get_settings

# 数据库文件路径
DB_PATH = Path(__file__).parent.parent / "data" / "v2t.db"


def generate_id() -> str:
    """生成安全随机 ID"""
    return secrets.token_urlsafe(16)


def normalize_url(url: str) -> str:
    """规范化 URL，去除参数"""
    parsed = urlparse(url)
    return f"{parsed.scheme}://{parsed.netloc}{parsed.path}"


# ============ 数据模型 ============

@dataclass
class UrlDownload:
    """URL 下载任务"""
    id: str
    original_url: str
    normalized_url: str
    download_url: Optional[str]
    video_id: Optional[str]
    status: str  # pending, downloading, completed
    created_at: str


@dataclass
class Video:
    """视频文件"""
    id: str
    title: Optional[str]
    video_path: Optional[str]
    duration: Optional[int]
    created_at: str


@dataclass
class Audio:
    """音频文件"""
    id: str
    title: Optional[str]
    audio_path: Optional[str]
    duration: Optional[int]
    created_at: str


@dataclass
class VideoAudioConversion:
    """视频转音频记录"""
    id: str
    video_id: str
    audio_id: str
    conversion_ms: Optional[int]  # 转换耗时（毫秒）
    created_at: str


@dataclass
class Transcript:
    """转录"""
    id: str
    audio_id: Optional[str]
    status: str
    content: Optional[str]
    created_at: str


@dataclass
class Outline:
    """大纲"""
    id: str
    transcript_id: str
    status: str
    content: Optional[str]
    created_at: str


@dataclass
class Article:
    """文章"""
    id: str
    transcript_id: str
    status: str
    content: Optional[str]
    created_at: str


# ============ 建表 SQL ============

INIT_SQL = """
-- URL 下载任务（URL -> Video 的映射）
CREATE TABLE IF NOT EXISTS url_downloads (
    id TEXT PRIMARY KEY,
    original_url TEXT NOT NULL,
    normalized_url TEXT UNIQUE NOT NULL,
    download_url TEXT,
    video_id TEXT REFERENCES videos(id) ON DELETE SET NULL,
    status TEXT DEFAULT 'pending',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 视频文件
CREATE TABLE IF NOT EXISTS videos (
    id TEXT PRIMARY KEY,
    title TEXT,
    video_path TEXT,
    duration INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 音频文件
CREATE TABLE IF NOT EXISTS audios (
    id TEXT PRIMARY KEY,
    title TEXT,
    audio_path TEXT,
    duration INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 视频转音频记录（video:audio = 1:1）
CREATE TABLE IF NOT EXISTS video_audio_conversions (
    id TEXT PRIMARY KEY,
    video_id TEXT UNIQUE NOT NULL REFERENCES videos(id) ON DELETE CASCADE,
    audio_id TEXT UNIQUE NOT NULL REFERENCES audios(id) ON DELETE CASCADE,
    conversion_ms INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 转录资源
CREATE TABLE IF NOT EXISTS transcripts (
    id TEXT PRIMARY KEY,
    audio_id TEXT REFERENCES audios(id) ON DELETE SET NULL,
    status TEXT DEFAULT 'pending',
    content TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 大纲资源
CREATE TABLE IF NOT EXISTS outlines (
    id TEXT PRIMARY KEY,
    transcript_id TEXT NOT NULL REFERENCES transcripts(id) ON DELETE CASCADE,
    status TEXT DEFAULT 'pending',
    content TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 文章资源
CREATE TABLE IF NOT EXISTS articles (
    id TEXT PRIMARY KEY,
    transcript_id TEXT NOT NULL REFERENCES transcripts(id) ON DELETE CASCADE,
    status TEXT DEFAULT 'pending',
    content TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 索引
CREATE INDEX IF NOT EXISTS idx_url_downloads_normalized_url ON url_downloads(normalized_url);
CREATE INDEX IF NOT EXISTS idx_url_downloads_video_id ON url_downloads(video_id);
CREATE INDEX IF NOT EXISTS idx_conversions_video_id ON video_audio_conversions(video_id);
CREATE INDEX IF NOT EXISTS idx_conversions_audio_id ON video_audio_conversions(audio_id);
CREATE INDEX IF NOT EXISTS idx_transcripts_audio_id ON transcripts(audio_id);
CREATE INDEX IF NOT EXISTS idx_outlines_transcript_id ON outlines(transcript_id);
CREATE INDEX IF NOT EXISTS idx_articles_transcript_id ON articles(transcript_id);
"""


async def init_db():
    """初始化数据库"""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    async with aiosqlite.connect(DB_PATH) as db:
        await db.executescript(INIT_SQL)
        await db.commit()


async def get_db() -> aiosqlite.Connection:
    """获取数据库连接"""
    db = await aiosqlite.connect(DB_PATH)
    db.row_factory = aiosqlite.Row
    return db

# ============ Generic DB Helpers ============

T = TypeVar("T")

async def _fetch_one(
    query: str,
    params: tuple,
    model_factory: callable
) -> Optional[Any]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(query, params)
        row = await cursor.fetchone()
        return model_factory(row) if row else None

async def _fetch_all(
    query: str,
    params: tuple,
    model_factory: callable
) -> List[Any]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(query, params)
        rows = await cursor.fetchall()
        return [model_factory(row) for row in rows]

async def _insert(
    table: str,
    data: dict
) -> None:
    keys = list(data.keys())
    placeholders = ", ".join(["?"] * len(keys))
    columns = ", ".join(keys)
    values = tuple(data.values())

    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            f"INSERT INTO {table} ({columns}) VALUES ({placeholders})",
            values
        )
        await db.commit()

async def _update(
    table: str,
    record_id: str,
    data: dict
) -> None:
    if not data:
        return

    fields = ", ".join(f"{k} = ?" for k in data.keys())
    values = list(data.values()) + [record_id]

    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(f"UPDATE {table} SET {fields} WHERE id = ?", values)
        await db.commit()

async def _delete(
    table: str,
    record_id: str
) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(f"DELETE FROM {table} WHERE id = ?", (record_id,))
        await db.commit()
        return cursor.rowcount > 0


# ============ UrlDownloads CRUD ============

def _row_to_url_download(row) -> UrlDownload:
    return UrlDownload(
        id=row["id"],
        original_url=row["original_url"],
        normalized_url=row["normalized_url"],
        download_url=row["download_url"],
        video_id=row["video_id"],
        status=row["status"],
        created_at=row["created_at"],
    )

async def create_url_download(original_url: str) -> tuple[UrlDownload, bool]:
    """
    创建 URL 下载任务
    返回 (url_download, created) - created 表示是否新创建
    """
    normalized = normalize_url(original_url)

    # 检查是否已存在
    existing = await _fetch_one(
        "SELECT * FROM url_downloads WHERE normalized_url = ?",
        (normalized,),
        _row_to_url_download
    )
    if existing:
        return existing, False

    # 创建新记录
    download_id = generate_id()
    await _insert(
        "url_downloads",
        {
            "id": download_id,
            "original_url": original_url,
            "normalized_url": normalized,
            "status": "pending"
        }
    )

    new_record = await get_url_download(download_id)
    return new_record, True


async def get_url_download(download_id: str) -> Optional[UrlDownload]:
    """获取 URL 下载任务"""
    return await _fetch_one(
        "SELECT * FROM url_downloads WHERE id = ?",
        (download_id,),
        _row_to_url_download
    )


async def update_url_download(download_id: str, **kwargs) -> Optional[UrlDownload]:
    """更新 URL 下载任务"""
    await _update("url_downloads", download_id, kwargs)
    return await get_url_download(download_id)


# ============ Videos CRUD ============

def _row_to_video(row) -> Video:
    return Video(
        id=row["id"],
        title=row["title"],
        video_path=row["video_path"],
        duration=row["duration"],
        created_at=row["created_at"],
    )

async def create_video(
    title: Optional[str] = None,
    video_path: Optional[str] = None,
    duration: Optional[int] = None,
) -> Video:
    """创建视频记录"""
    video_id = generate_id()
    await _insert(
        "videos",
        {
            "id": video_id,
            "title": title,
            "video_path": video_path,
            "duration": duration
        }
    )
    return await get_video(video_id)


async def get_video(video_id: str) -> Optional[Video]:
    """获取视频"""
    return await _fetch_one(
        "SELECT * FROM videos WHERE id = ?",
        (video_id,),
        _row_to_video
    )


async def update_video(video_id: str, **kwargs) -> Optional[Video]:
    """更新视频"""
    await _update("videos", video_id, kwargs)
    return await get_video(video_id)


async def delete_video(video_id: str) -> bool:
    """删除视频"""
    return await _delete("videos", video_id)


# ============ Audios CRUD ============

def _row_to_audio(row) -> Audio:
    return Audio(
        id=row["id"],
        title=row["title"],
        audio_path=row["audio_path"],
        duration=row["duration"],
        created_at=row["created_at"],
    )

async def create_audio(
    title: Optional[str] = None,
    audio_path: Optional[str] = None,
    duration: Optional[int] = None,
) -> Audio:
    """创建音频记录"""
    audio_id = generate_id()
    await _insert(
        "audios",
        {
            "id": audio_id,
            "title": title,
            "audio_path": audio_path,
            "duration": duration
        }
    )
    return await get_audio(audio_id)


async def get_audio(audio_id: str) -> Optional[Audio]:
    """获取音频"""
    return await _fetch_one(
        "SELECT * FROM audios WHERE id = ?",
        (audio_id,),
        _row_to_audio
    )


async def update_audio(audio_id: str, **kwargs) -> Optional[Audio]:
    """更新音频"""
    await _update("audios", audio_id, kwargs)
    return await get_audio(audio_id)


async def delete_audio(audio_id: str) -> bool:
    """删除音频"""
    return await _delete("audios", audio_id)


# ============ VideoAudioConversions CRUD ============

def _row_to_conversion(row) -> VideoAudioConversion:
    return VideoAudioConversion(
        id=row["id"],
        video_id=row["video_id"],
        audio_id=row["audio_id"],
        conversion_ms=row["conversion_ms"],
        created_at=row["created_at"],
    )

async def create_video_audio_conversion(
    video_id: str,
    audio_id: str,
    conversion_ms: Optional[int] = None,
) -> VideoAudioConversion:
    """创建视频转音频记录"""
    conversion_id = generate_id()
    await _insert(
        "video_audio_conversions",
        {
            "id": conversion_id,
            "video_id": video_id,
            "audio_id": audio_id,
            "conversion_ms": conversion_ms
        }
    )
    return await get_conversion(conversion_id)


async def get_conversion(conversion_id: str) -> Optional[VideoAudioConversion]:
    """获取转换记录"""
    return await _fetch_one(
        "SELECT * FROM video_audio_conversions WHERE id = ?",
        (conversion_id,),
        _row_to_conversion
    )


async def get_conversion_by_video(video_id: str) -> Optional[VideoAudioConversion]:
    """根据 video_id 获取转换记录（1:1 关系）"""
    return await _fetch_one(
        "SELECT * FROM video_audio_conversions WHERE video_id = ?",
        (video_id,),
        _row_to_conversion
    )


async def get_conversion_by_audio(audio_id: str) -> Optional[VideoAudioConversion]:
    """根据 audio_id 获取转换记录（1:1 关系）"""
    return await _fetch_one(
        "SELECT * FROM video_audio_conversions WHERE audio_id = ?",
        (audio_id,),
        _row_to_conversion
    )


async def get_audio_by_video(video_id: str) -> Optional[Audio]:
    """根据 video_id 获取关联的音频（通过转换表）"""
    return await _fetch_one(
        """SELECT a.* FROM audios a
           JOIN video_audio_conversions c ON a.id = c.audio_id
           WHERE c.video_id = ?""",
        (video_id,),
        _row_to_audio
    )


# ============ Transcripts CRUD ============

def _row_to_transcript(row) -> Transcript:
    return Transcript(
        id=row["id"],
        audio_id=row["audio_id"],
        status=row["status"],
        content=row["content"],
        created_at=row["created_at"],
    )

async def create_transcript(audio_id: Optional[str] = None) -> Transcript:
    """创建转录记录"""
    transcript_id = generate_id()
    await _insert(
        "transcripts",
        {
            "id": transcript_id,
            "audio_id": audio_id,
            "status": "pending"
        }
    )
    return await get_transcript(transcript_id)


async def get_transcript(transcript_id: str) -> Optional[Transcript]:
    """获取转录"""
    return await _fetch_one(
        "SELECT * FROM transcripts WHERE id = ?",
        (transcript_id,),
        _row_to_transcript
    )


async def get_transcript_by_audio(audio_id: str) -> Optional[Transcript]:
    """根据 audio_id 获取转录"""
    return await _fetch_one(
        "SELECT * FROM transcripts WHERE audio_id = ? ORDER BY created_at DESC LIMIT 1",
        (audio_id,),
        _row_to_transcript
    )


async def update_transcript(transcript_id: str, **kwargs) -> Optional[Transcript]:
    """更新转录"""
    await _update("transcripts", transcript_id, kwargs)
    return await get_transcript(transcript_id)


# ============ Outlines CRUD ============

def _row_to_outline(row) -> Outline:
    return Outline(
        id=row["id"],
        transcript_id=row["transcript_id"],
        status=row["status"],
        content=row["content"],
        created_at=row["created_at"],
    )

async def create_outline(transcript_id: str) -> Outline:
    """创建大纲记录"""
    outline_id = generate_id()
    await _insert(
        "outlines",
        {
            "id": outline_id,
            "transcript_id": transcript_id,
            "status": "pending"
        }
    )
    return await get_outline(outline_id)


async def get_outline(outline_id: str) -> Optional[Outline]:
    """获取大纲"""
    return await _fetch_one(
        "SELECT * FROM outlines WHERE id = ?",
        (outline_id,),
        _row_to_outline
    )


async def get_outline_by_transcript(transcript_id: str) -> Optional[Outline]:
    """根据 transcript_id 获取大纲"""
    return await _fetch_one(
        "SELECT * FROM outlines WHERE transcript_id = ? ORDER BY created_at DESC LIMIT 1",
        (transcript_id,),
        _row_to_outline
    )


async def update_outline(outline_id: str, **kwargs) -> Optional[Outline]:
    """更新大纲"""
    await _update("outlines", outline_id, kwargs)
    return await get_outline(outline_id)


# ============ Articles CRUD ============

def _row_to_article(row) -> Article:
    return Article(
        id=row["id"],
        transcript_id=row["transcript_id"],
        status=row["status"],
        content=row["content"],
        created_at=row["created_at"],
    )

async def create_article(transcript_id: str) -> Article:
    """创建文章记录"""
    article_id = generate_id()
    await _insert(
        "articles",
        {
            "id": article_id,
            "transcript_id": transcript_id,
            "status": "pending"
        }
    )
    return await get_article(article_id)


async def get_article(article_id: str) -> Optional[Article]:
    """获取文章"""
    return await _fetch_one(
        "SELECT * FROM articles WHERE id = ?",
        (article_id,),
        _row_to_article
    )


async def get_article_by_transcript(transcript_id: str) -> Optional[Article]:
    """根据 transcript_id 获取文章"""
    return await _fetch_one(
        "SELECT * FROM articles WHERE transcript_id = ? ORDER BY created_at DESC LIMIT 1",
        (transcript_id,),
        _row_to_article
    )


async def update_article(article_id: str, **kwargs) -> Optional[Article]:
    """更新文章"""
    await _update("articles", article_id, kwargs)
    return await get_article(article_id)
