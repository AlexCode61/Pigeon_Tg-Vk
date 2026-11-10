from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.ext.asyncio import async_sessionmaker
from sqlalchemy import text

from pigeon_tg_vk.bridge.config import get_required_env
from pigeon_tg_vk.bridge.storage.base import Base

DATABASE_URL = f"postgresql+asyncpg://{get_required_env('POSTGRES_USER')}:{get_required_env('POSTGRES_PASSWORD')}@{get_required_env('POSTGRES_HOST')}:{get_required_env('POSTGRES_PORT')}/{get_required_env('POSTGRES_DB')}"

engine = create_async_engine(
    DATABASE_URL, 
    echo=False
)

async_session_maker = async_sessionmaker(bind=engine, expire_on_commit=False)

async def create_database_tables() -> None:
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

async def check_database_connection():
    async with engine.connect() as connection:
        result = await connection.execute(text("Select 1"))
        return result.scalar_one() == 1

async def close_database()-> None:
    await engine.dispose()