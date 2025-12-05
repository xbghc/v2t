"""数据库连接管理"""

from pathlib import Path
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase

# 数据库文件路径
DB_PATH = Path.home() / ".config" / "v2t" / "v2t.db"


class Base(DeclarativeBase):
    """SQLAlchemy 基类"""
    pass


# 确保目录存在
DB_PATH.parent.mkdir(parents=True, exist_ok=True)

# 创建异步引擎
engine = create_async_engine(
    f"sqlite+aiosqlite:///{DB_PATH}",
    echo=False,
)

# 创建会话工厂
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def init_db():
    """初始化数据库表"""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_db() -> AsyncSession:
    """获取数据库会话（用于依赖注入）"""
    async with AsyncSessionLocal() as session:
        yield session
