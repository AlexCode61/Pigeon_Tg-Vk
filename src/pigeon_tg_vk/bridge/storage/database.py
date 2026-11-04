from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.ext.asyncio import async_sessionmaker

from pigeon_tg_vk.bridge.config import get_required_env

DATABASE_URL = f"postgresql+asyncpg://{get_required_env('DATABASE_USER')}:{get_required_env('DATABASE_PASSWORD')}@{get_required_env('DATABASE_ADDRESS')}/{get_required_env('DATABASE_NAME')}"

engine = create_async_engine(
    DATABASE_URL, 
    echo=False
)

async_session_maker = async_sessionmaker(bind=engine, expire_on_commit=False)