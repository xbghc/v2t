"""v2t Web API 服务入口"""

# 加载 .env 文件（必须在其他模块导入前执行）
from dotenv import load_dotenv

load_dotenv()

# 配置日志（必须在其他模块导入前执行）
from app.logging_config import setup_logging

setup_logging()

# 标准库
import asyncio
from contextlib import asynccontextmanager

# 第三方库
from fastapi import Depends, FastAPI
from loguru import logger

from app.constants import API_V1_PREFIX
from app.dependencies import require_user
from app.routers import (
    admin_router,
    auth_router,
    bilibili_router,
    diagnostics_router,
    media_router,
    metrics_router,
    prompts_router,
    stream_router,
    workspace_router,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 启动：建 Mongo 索引（失败不阻止启动——mongo 可能尚未就绪）
    try:
        from app.storage.user_store import ensure_indexes

        await ensure_indexes()
        logger.info("Mongo 索引已就绪")
    except Exception as e:
        logger.warning("建立 Mongo 索引失败（mongo 未就绪？）: {}", e)
    yield


app = FastAPI(
    title="v2t - 视频转文字",
    description="输入视频链接，获取视频、音频、大纲和详细文字",
    lifespan=lifespan,
)

# 对外 API：统一挂在 /api/v1，版本号集中此处控制（开 v2 时复制此块改前缀）。
# 这些是会被不可控客户端（桌面/移动端）调用的版本化契约。
app.include_router(auth_router, prefix=API_V1_PREFIX)  # 登录端点本身不鉴权
# 其余对外端点全部要求登录（require_user）——未登录返回 401，前端据此跳登录
_AUTH = [Depends(require_user)]
app.include_router(workspace_router, prefix=API_V1_PREFIX, dependencies=_AUTH)
app.include_router(stream_router, prefix=API_V1_PREFIX, dependencies=_AUTH)
app.include_router(prompts_router, prefix=API_V1_PREFIX, dependencies=_AUTH)
app.include_router(media_router, prefix=API_V1_PREFIX, dependencies=_AUTH)
app.include_router(bilibili_router, prefix=API_V1_PREFIX, dependencies=_AUTH)
# 内部端点：不版本化，路径保持 /api/...。metrics 公开（前端 PV/UV 上报）；
# diag/admin 靠 nginx-docker.conf 按 /api/diag、/api/admin 路径对公网 404 隔离，
# 故这三者前缀必须保持不变，不能并入 /api/v1。
app.include_router(metrics_router)
app.include_router(diagnostics_router)
app.include_router(admin_router)


async def check_redis_connection() -> tuple[bool, str]:
    """检测 Redis 连接状态（必需配置）"""
    from app.config import get_settings
    from app.storage import get_metadata_store

    settings = get_settings()

    if not settings.redis_url:
        return False, "未配置 REDIS_URL 环境变量"

    store = get_metadata_store()
    return await store.check_connection()


async def check_api_connections() -> bool:
    """检测所有 API 连接，返回是否全部成功"""
    from app.services.llm import check_llm_api
    from app.services.podcast_tts import check_tts_api
    from app.services.transcribe import check_stt_api
    from app.services.xiazaitool import check_xiazaitool_token

    # 检查 Redis 连接
    ok, msg = await check_redis_connection()
    if ok:
        logger.info("✓ Redis: {}", msg)
    else:
        logger.error("✗ Redis: {}", msg)
        return False

    # 同步检查（配置检测）
    ok, msg = check_xiazaitool_token()
    if ok:
        logger.info("✓ Xiazaitool: {}", msg)
    else:
        logger.error("✗ Xiazaitool: {}", msg)
        return False

    # 异步检查（API 连接检测）
    checks = [
        ("LLM", check_llm_api()),
        ("STT", check_stt_api()),
        ("TTS", check_tts_api()),
    ]

    all_ok = True
    for name, coro in checks:
        ok, msg = await coro
        if ok:
            logger.info("✓ {} API: {}", name, msg)
        else:
            logger.error("✗ {} API: {}", name, msg)
            all_ok = False

    return all_ok


def run_server(host: str = "0.0.0.0", port: int = 8103) -> None:
    """启动服务器"""
    from app.deps import check_dependencies, get_install_hint

    missing = check_dependencies()
    if missing:
        deps_str = ", ".join(f"{cmd} ({desc})" for cmd, desc in missing)
        logger.error("缺少系统依赖: {}", deps_str)
        logger.error(get_install_hint())
        raise SystemExit(1)

    # 检测 API 连接
    if not asyncio.run(check_api_connections()):
        logger.error("API 检测失败，服务无法启动")
        raise SystemExit(1)

    # 重置存储单例，避免客户端绑定到已关闭的事件循环
    from app.storage import reset_stores

    reset_stores()

    import uvicorn

    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    run_server()
