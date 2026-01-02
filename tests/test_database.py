import pytest
import aiosqlite
from pathlib import Path
from app import database

# Use a temporary database for testing
TEST_DB_PATH = Path("test_v2t.db")

@pytest.fixture(autouse=True)
async def setup_database():
    """Setup and teardown database for each test"""
    # Patch DB_PATH
    database.DB_PATH = TEST_DB_PATH

    # Initialize DB
    await database.init_db()

    yield

    # Cleanup
    if TEST_DB_PATH.exists():
        TEST_DB_PATH.unlink()

@pytest.mark.asyncio
async def test_url_download_crud():
    original_url = "http://example.com/video?param=1"

    # Create
    url_download, created = await database.create_url_download(original_url)
    assert created
    assert url_download.original_url == original_url
    assert url_download.normalized_url == "http://example.com/video"
    assert url_download.status == "pending"
    assert url_download.id is not None

    # Create Duplicate
    url_download_dup, created = await database.create_url_download(original_url)
    assert not created
    assert url_download_dup.id == url_download.id

    # Get
    fetched = await database.get_url_download(url_download.id)
    assert fetched is not None
    assert fetched.id == url_download.id

    # Update
    updated = await database.update_url_download(
        url_download.id,
        status="completed",
        download_url="http://example.com/file.mp4"
    )
    assert updated.status == "completed"
    assert updated.download_url == "http://example.com/file.mp4"

    # Get Updated
    fetched_updated = await database.get_url_download(url_download.id)
    assert fetched_updated.status == "completed"

@pytest.mark.asyncio
async def test_video_crud():
    # Create
    video = await database.create_video(title="Test Video", duration=120)
    assert video.title == "Test Video"
    assert video.duration == 120
    assert video.id is not None

    # Get
    fetched = await database.get_video(video.id)
    assert fetched.id == video.id

    # Update
    updated = await database.update_video(video.id, title="Updated Title")
    assert updated.title == "Updated Title"

    # Delete
    deleted = await database.delete_video(video.id)
    assert deleted

    fetched_deleted = await database.get_video(video.id)
    assert fetched_deleted is None

@pytest.mark.asyncio
async def test_audio_crud():
    # Create
    audio = await database.create_audio(title="Test Audio", duration=60)
    assert audio.title == "Test Audio"
    assert audio.duration == 60
    assert audio.id is not None

    # Get
    fetched = await database.get_audio(audio.id)
    assert fetched.id == audio.id

    # Update
    updated = await database.update_audio(audio.id, title="Updated Audio")
    assert updated.title == "Updated Audio"

    # Delete
    deleted = await database.delete_audio(audio.id)
    assert deleted

    fetched_deleted = await database.get_audio(audio.id)
    assert fetched_deleted is None

@pytest.mark.asyncio
async def test_conversion_crud():
    video = await database.create_video(title="v1")
    audio = await database.create_audio(title="a1")

    # Create
    conversion = await database.create_video_audio_conversion(
        video.id, audio.id, conversion_ms=1000
    )
    assert conversion.video_id == video.id
    assert conversion.audio_id == audio.id

    # Get
    fetched = await database.get_conversion(conversion.id)
    assert fetched.id == conversion.id

    # Get by video/audio
    by_video = await database.get_conversion_by_video(video.id)
    assert by_video.id == conversion.id

    by_audio = await database.get_conversion_by_audio(audio.id)
    assert by_audio.id == conversion.id

    # Get audio by video
    fetched_audio = await database.get_audio_by_video(video.id)
    assert fetched_audio.id == audio.id

@pytest.mark.asyncio
async def test_transcript_crud():
    audio = await database.create_audio(title="a1")

    # Create
    transcript = await database.create_transcript(audio.id)
    assert transcript.audio_id == audio.id
    assert transcript.status == "pending"

    # Get
    fetched = await database.get_transcript(transcript.id)
    assert fetched.id == transcript.id

    # Get by audio
    by_audio = await database.get_transcript_by_audio(audio.id)
    assert by_audio.id == transcript.id

    # Update
    updated = await database.update_transcript(transcript.id, status="completed", content="Hello")
    assert updated.status == "completed"
    assert updated.content == "Hello"

@pytest.mark.asyncio
async def test_outline_crud():
    transcript = await database.create_transcript()

    # Create
    outline = await database.create_outline(transcript.id)
    assert outline.transcript_id == transcript.id
    assert outline.status == "pending"

    # Get
    fetched = await database.get_outline(outline.id)
    assert fetched.id == outline.id

    # Get by transcript
    by_transcript = await database.get_outline_by_transcript(transcript.id)
    assert by_transcript.id == outline.id

    # Update
    updated = await database.update_outline(outline.id, status="completed", content="Outline 1")
    assert updated.status == "completed"
    assert updated.content == "Outline 1"

@pytest.mark.asyncio
async def test_article_crud():
    transcript = await database.create_transcript()

    # Create
    article = await database.create_article(transcript.id)
    assert article.transcript_id == transcript.id
    assert article.status == "pending"

    # Get
    fetched = await database.get_article(article.id)
    assert fetched.id == article.id

    # Get by transcript
    by_transcript = await database.get_article_by_transcript(transcript.id)
    assert by_transcript.id == article.id

    # Update
    updated = await database.update_article(article.id, status="completed", content="Article 1")
    assert updated.status == "completed"
    assert updated.content == "Article 1"
