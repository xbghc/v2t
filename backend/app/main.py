"""v2t Web API 服务入口"""

# 加载 .env 文件（必须在其他模块导入前执行）
from dotenv import load_dotenv

load_dotenv()

# 配置日志（必须在其他模块导入前执行）
from app.logging_config import setup_logging

setup_logging()

# 标准库
import asyncio

# 第三方库
from fastapi import FastAPI
from loguru import logger

from app.routers import (
    prompts_router,
    stream_router,
    workspace_router,
)

app = FastAPI(
    title="v2t - 视频转文字",
    description="输入视频链接，获取视频、音频、大纲和详细文字",
)

# 注册路由
app.include_router(workspace_router)
app.include_router(stream_router)
app.include_router(prompts_router)


async def check_mongodb_connection() -> tuple[bool, str]:
    """检测 MongoDB 连接状态"""
    from app.config import get_settings
    from app.storage import get_metadata_store

    settings = get_settings()

    # 未配置 MongoDB，使用内存存储
    if not settings.mongodb_uri:
        return True, "使用内存存储（未配置 MONGODB_URI）"

    # 检查 MongoDB 连接
    store = get_metadata_store()

    # MongoMetadataStore 有 check_connection 方法
    if hasattr(store, "check_connection"):
        return await store.check_connection()

    return True, "使用内存存储"


async def check_api_connections() -> bool:
    """检测所有 API 连接，返回是否全部成功"""
    from app.services.llm import check_llm_api
    from app.services.podcast_tts import check_tts_api
    from app.services.transcribe import check_whisper_api
    from app.services.xiazaitool import check_xiazaitool_token

    # 检查 MongoDB 连接
    ok, msg = await check_mongodb_connection()
    if ok:
        logger.info("✓ MongoDB: %s", msg)
    else:
        logger.error("✗ MongoDB: %s", msg)
        return False

    # 同步检查（配置检测）
    ok, msg = check_xiazaitool_token()
    if ok:
        logger.info("✓ Xiazaitool: %s", msg)
    else:
        logger.error("✗ Xiazaitool: %s", msg)
        return False

    # 异步检查（API 连接检测）
    checks = [
        ("LLM", check_llm_api()),
        ("Whisper", check_whisper_api()),
        ("TTS", check_tts_api()),
    ]

    all_ok = True
    for name, coro in checks:
        ok, msg = await coro
        if ok:
            logger.info("✓ %s API: %s", name, msg)
        else:
            logger.error("✗ %s API: %s", name, msg)
            all_ok = False

    return all_ok


def run_server(host: str = "0.0.0.0", port: int = 8101) -> None:
    """启动服务器"""
    from app.deps import check_dependencies, get_install_hint

    missing = check_dependencies()
    if missing:
        deps_str = ", ".join(f"{cmd} ({desc})" for cmd, desc in missing)
        logger.error("缺少系统依赖: %s", deps_str)
        logger.error(get_install_hint())
        raise SystemExit(1)

    # 检测 API 连接
    if not asyncio.run(check_api_connections()):
        logger.error("API 检测失败，服务无法启动")
        raise SystemExit(1)

    import uvicorn

    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    run_server()
