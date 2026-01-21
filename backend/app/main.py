"""v2t Web API 服务入口"""

import asyncio
import logging
import os

# 配置日志（支持 LOG_LEVEL 环境变量：DEBUG/INFO/WARNING/ERROR）
log_level_name = os.environ.get("LOG_LEVEL", "INFO").upper()
log_level = getattr(logging, log_level_name, logging.INFO)

logging.basicConfig(
    level=log_level,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

from fastapi import FastAPI

from app.routers import (
    process_router,
    prompts_router,
    resource_router,
    stream_router,
    task_router,
)

app = FastAPI(
    title="v2t - 视频转文字",
    description="输入视频链接，获取视频、音频、大纲和详细文字",
)

# 注册路由
app.include_router(process_router)
app.include_router(task_router)
app.include_router(stream_router)
app.include_router(resource_router)
app.include_router(prompts_router)


async def check_api_connections() -> bool:
    """检测所有 API 连接，返回是否全部成功"""
    from app.services.llm import check_llm_api
    from app.services.podcast_tts import check_tts_api
    from app.services.transcribe import check_whisper_api

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
