import os
from pathlib import Path
from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, declarative_base

# 1. Cargar variables de entorno
BASE_DIR = Path(__file__).resolve().parents[1]
ROOT_DIR = BASE_DIR.parent
load_dotenv(ROOT_DIR / ".env")
load_dotenv(BASE_DIR / ".env", override=True)

# 2. Configurar la URL de conexión
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+asyncpg://postgres:postgres@localhost:5432/constructo_db")

# Asegurar que usamos el driver asíncrono
if DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://", 1)

SQLALCHEMY_ECHO = os.getenv("SQLALCHEMY_ECHO", "false").lower() in {"1", "true", "yes", "on"}

# 3. Crear el Motor Asíncrono
engine = create_async_engine(DATABASE_URL, echo=SQLALCHEMY_ECHO)

# 4. Configurar la Fábrica de Sesiones
SessionLocal = sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False
)

# 5. Base para los Modelos
Base = declarative_base()

# 6. Dependencia para FastAPI
async def get_db():
    async with SessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()