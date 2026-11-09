import json
from typing import AsyncGenerator, Optional
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import select
from backend.app.core.config import settings
from database.models import Base, SystemLog, SystemSetting

# Ensure parent directory for sqlite exists
settings.STORAGE_DIR.mkdir(parents=True, exist_ok=True)
settings.DOWNLOADS_DIR.mkdir(parents=True, exist_ok=True)
settings.THUMBNAILS_DIR.mkdir(parents=True, exist_ok=True)
settings.LOGS_DIR.mkdir(parents=True, exist_ok=True)

engine = create_async_engine(
    settings.DATABASE_URL,
    echo=False,
    future=True
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False
)

async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()

async def log_event(category: str, level: str, message: str, details: Optional[str | dict] = None):
    async with AsyncSessionLocal() as session:
        try:
            details_str = json.dumps(details, ensure_ascii=False) if isinstance(details, dict) else details
            log_entry = SystemLog(
                category=category.upper(),
                level=level.upper(),
                message=message,
                details=details_str
            )
            session.add(log_entry)
            await session.commit()
        except Exception as e:
            print(f"[LOG_ERROR] Could not write log: {e}")

async def get_setting(key: str, default: Optional[str] = None) -> Optional[str]:
    async with AsyncSessionLocal() as session:
        stmt = select(SystemSetting).where(SystemSetting.key == key)
        res = await session.execute(stmt)
        record = res.scalar_one_or_none()
        return record.value if record and record.value is not None else default

async def set_setting(key: str, value: str):
    async with AsyncSessionLocal() as session:
        stmt = select(SystemSetting).where(SystemSetting.key == key)
        res = await session.execute(stmt)
        record = res.scalar_one_or_none()
        if record:
            record.value = value
        else:
            session.add(SystemSetting(key=key, value=value))
        await session.commit()
