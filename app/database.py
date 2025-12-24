"""SQLite 数据库操作层"""

import aiosqlite
import uuid
from pathlib import Path
from urllib.parse import urlparse
from dataclasses import dataclass
from typing import Optional
from datetime import datetime

from app.config import get_settings

# 数据库文件路径
DB_PATH = Path(__file__).parent.parent / "data" / "v2t.db"


def generate_id() -> str:
    """生成 8 位 UUID"""
    return str(uuid.uuid4())[:8]


def normalize_url(url: str) -> str:
    """规范化 URL，去除参数"""
    parsed = urlparse(url)
    return f"{parsed.scheme}://{parsed.netloc}{parsed.path}"


# 数据模型
@dataclass
class Video:
    id: str
    original_url: Optional[str]
    normalized_url: Optional[str]
    download_url: Optional[str]
    title: Optional[str]
    status: str
    video_path: Optional[str]
    audio_path: Optional[str]
    created_at: str


@dataclass
class Transcript:
    id: str
    video_id: Optional[str]
    status: str
    content: Optional[str]
    created_at: str


@dataclass
class Outline:
    id: str
    transcript_id: str
    status: str
    content: Optional[str]
    created_at: str


@dataclass
class Article:
    id: str
    transcript_id: str
    status: str
    content: Optional[str]
    created_at: str


# 建表 SQL
INIT_SQL = """
-- 视频资源
CREATE TABLE IF NOT EXISTS videos (
    id TEXT PRIMARY KEY,
    original_url TEXT,
    normalized_url TEXT UNIQUE,
    download_url TEXT,
    title TEXT,
    status TEXT DEFAULT 'pending',
    video_path TEXT,
    audio_path TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 转录资源
CREATE TABLE IF NOT EXISTS transcripts (
    id TEXT PRIMARY KEY,
    video_id TEXT REFERENCES videos(id) ON DELETE SET NULL,
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
CREATE INDEX IF NOT EXISTS idx_videos_normalized_url ON videos(normalized_url);
CREATE INDEX IF NOT EXISTS idx_transcripts_video_id ON transcripts(video_id);
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


# ============ Videos CRUD ============

async def create_video(original_url: str) -> tuple[Video, bool]:
    """
    创建视频记录
    返回 (video, created) - created 表示是否新创建
    """
    normalized = normalize_url(original_url)

    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row

        # 检查是否已存在
        cursor = await db.execute(
            "SELECT * FROM videos WHERE normalized_url = ?",
            (normalized,)
        )
        row = await cursor.fetchone()

        if row:
            return _row_to_video(row), False

        # 创建新记录
        video_id = generate_id()
        await db.execute(
            """INSERT INTO videos (id, original_url, normalized_url, status)
               VALUES (?, ?, ?, 'pending')""",
            (video_id, original_url, normalized)
        )
        await db.commit()

        cursor = await db.execute("SELECT * FROM videos WHERE id = ?", (video_id,))
        row = await cursor.fetchone()
        return _row_to_video(row), True


async def get_video(video_id: str) -> Optional[Video]:
    """获取视频"""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT * FROM videos WHERE id = ?", (video_id,))
        row = await cursor.fetchone()
        return _row_to_video(row) if row else None


async def update_video(video_id: str, **kwargs) -> Optional[Video]:
    """更新视频"""
    if not kwargs:
        return await get_video(video_id)

    fields = ", ".join(f"{k} = ?" for k in kwargs.keys())
    values = list(kwargs.values()) + [video_id]

    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        await db.execute(f"UPDATE videos SET {fields} WHERE id = ?", values)
        await db.commit()

        cursor = await db.execute("SELECT * FROM videos WHERE id = ?", (video_id,))
        row = await cursor.fetchone()
        return _row_to_video(row) if row else None


async def delete_video(video_id: str) -> bool:
    """删除视频"""
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("DELETE FROM videos WHERE id = ?", (video_id,))
        await db.commit()
        return cursor.rowcount > 0


def _row_to_video(row) -> Video:
    return Video(
        id=row["id"],
        original_url=row["original_url"],
        normalized_url=row["normalized_url"],
        download_url=row["download_url"],
        title=row["title"],
        status=row["status"],
        video_path=row["video_path"],
        audio_path=row["audio_path"],
        created_at=row["created_at"],
    )


# ============ Transcripts CRUD ============

async def create_transcript(video_id: Optional[str] = None) -> Transcript:
    """创建转录记录"""
    transcript_id = generate_id()

    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        await db.execute(
            """INSERT INTO transcripts (id, video_id, status)
               VALUES (?, ?, 'pending')""",
            (transcript_id, video_id)
        )
        await db.commit()

        cursor = await db.execute("SELECT * FROM transcripts WHERE id = ?", (transcript_id,))
        row = await cursor.fetchone()
        return _row_to_transcript(row)


async def get_transcript(transcript_id: str) -> Optional[Transcript]:
    """获取转录"""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT * FROM transcripts WHERE id = ?", (transcript_id,))
        row = await cursor.fetchone()
        return _row_to_transcript(row) if row else None


async def get_transcript_by_video(video_id: str) -> Optional[Transcript]:
    """根据 video_id 获取转录"""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM transcripts WHERE video_id = ? ORDER BY created_at DESC LIMIT 1",
            (video_id,)
        )
        row = await cursor.fetchone()
        return _row_to_transcript(row) if row else None


async def update_transcript(transcript_id: str, **kwargs) -> Optional[Transcript]:
    """更新转录"""
    if not kwargs:
        return await get_transcript(transcript_id)

    fields = ", ".join(f"{k} = ?" for k in kwargs.keys())
    values = list(kwargs.values()) + [transcript_id]

    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        await db.execute(f"UPDATE transcripts SET {fields} WHERE id = ?", values)
        await db.commit()

        cursor = await db.execute("SELECT * FROM transcripts WHERE id = ?", (transcript_id,))
        row = await cursor.fetchone()
        return _row_to_transcript(row) if row else None


def _row_to_transcript(row) -> Transcript:
    return Transcript(
        id=row["id"],
        video_id=row["video_id"],
        status=row["status"],
        content=row["content"],
        created_at=row["created_at"],
    )


# ============ Outlines CRUD ============

async def create_outline(transcript_id: str) -> Outline:
    """创建大纲记录"""
    outline_id = generate_id()

    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        await db.execute(
            """INSERT INTO outlines (id, transcript_id, status)
               VALUES (?, ?, 'pending')""",
            (outline_id, transcript_id)
        )
        await db.commit()

        cursor = await db.execute("SELECT * FROM outlines WHERE id = ?", (outline_id,))
        row = await cursor.fetchone()
        return _row_to_outline(row)


async def get_outline(outline_id: str) -> Optional[Outline]:
    """获取大纲"""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT * FROM outlines WHERE id = ?", (outline_id,))
        row = await cursor.fetchone()
        return _row_to_outline(row) if row else None


async def get_outline_by_transcript(transcript_id: str) -> Optional[Outline]:
    """根据 transcript_id 获取大纲"""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM outlines WHERE transcript_id = ? ORDER BY created_at DESC LIMIT 1",
            (transcript_id,)
        )
        row = await cursor.fetchone()
        return _row_to_outline(row) if row else None


async def update_outline(outline_id: str, **kwargs) -> Optional[Outline]:
    """更新大纲"""
    if not kwargs:
        return await get_outline(outline_id)

    fields = ", ".join(f"{k} = ?" for k in kwargs.keys())
    values = list(kwargs.values()) + [outline_id]

    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        await db.execute(f"UPDATE outlines SET {fields} WHERE id = ?", values)
        await db.commit()

        cursor = await db.execute("SELECT * FROM outlines WHERE id = ?", (outline_id,))
        row = await cursor.fetchone()
        return _row_to_outline(row) if row else None


def _row_to_outline(row) -> Outline:
    return Outline(
        id=row["id"],
        transcript_id=row["transcript_id"],
        status=row["status"],
        content=row["content"],
        created_at=row["created_at"],
    )


# ============ Articles CRUD ============

async def create_article(transcript_id: str) -> Article:
    """创建文章记录"""
    article_id = generate_id()

    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        await db.execute(
            """INSERT INTO articles (id, transcript_id, status)
               VALUES (?, ?, 'pending')""",
            (article_id, transcript_id)
        )
        await db.commit()

        cursor = await db.execute("SELECT * FROM articles WHERE id = ?", (article_id,))
        row = await cursor.fetchone()
        return _row_to_article(row)


async def get_article(article_id: str) -> Optional[Article]:
    """获取文章"""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT * FROM articles WHERE id = ?", (article_id,))
        row = await cursor.fetchone()
        return _row_to_article(row) if row else None


async def get_article_by_transcript(transcript_id: str) -> Optional[Article]:
    """根据 transcript_id 获取文章"""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM articles WHERE transcript_id = ? ORDER BY created_at DESC LIMIT 1",
            (transcript_id,)
        )
        row = await cursor.fetchone()
        return _row_to_article(row) if row else None


async def update_article(article_id: str, **kwargs) -> Optional[Article]:
    """更新文章"""
    if not kwargs:
        return await get_article(article_id)

    fields = ", ".join(f"{k} = ?" for k in kwargs.keys())
    values = list(kwargs.values()) + [article_id]

    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        await db.execute(f"UPDATE articles SET {fields} WHERE id = ?", values)
        await db.commit()

        cursor = await db.execute("SELECT * FROM articles WHERE id = ?", (article_id,))
        row = await cursor.fetchone()
        return _row_to_article(row) if row else None


def _row_to_article(row) -> Article:
    return Article(
        id=row["id"],
        transcript_id=row["transcript_id"],
        status=row["status"],
        content=row["content"],
        created_at=row["created_at"],
    )
