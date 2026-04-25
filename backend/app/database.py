import os
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, declarative_base

# 1. Cargar variables de entorno (para seguridad de credenciales)
# Se carga primero desde la raiz del proyecto y luego desde backend/.env (si existe),
# permitiendo sobreescritura local especifica para el backend.
BASE_DIR = Path(__file__).resolve().parents[1]  # backend/
ROOT_DIR = BASE_DIR.parent
load_dotenv(ROOT_DIR / ".env")
load_dotenv(BASE_DIR / ".env", override=True)

# 2. Configurar la URL de conexión
DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:

    DATABASE_URL = "postgresql+asyncpg://postgres:postgres@localhost:5432/constructo_db"

# Permite usar `postgresql://` en .env sin romper create_async_engine.
if DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://", 1)


def normalize_asyncpg_url(url: str) -> str:
    """Adapta query params estilo libpq para asyncpg."""
    parts = urlsplit(url)
    query = dict(parse_qsl(parts.query, keep_blank_values=True))

    if "sslmode" in query and "ssl" not in query:
        query["ssl"] = query["sslmode"]

    query.pop("sslmode", None)
    query.pop("channel_binding", None)

    new_query = urlencode(query)
    return urlunsplit((parts.scheme, parts.netloc, parts.path, new_query, parts.fragment))


if DATABASE_URL.startswith("postgresql+asyncpg://"):
    DATABASE_URL = normalize_asyncpg_url(DATABASE_URL)

SQLALCHEMY_ECHO = os.getenv("SQLALCHEMY_ECHO", "false").lower() in {"1", "true", "yes", "on"}

# 3. Crear el Motor Asíncrono
# SQLALCHEMY_ECHO=true permite ver las consultas SQL en la terminal
engine = create_async_engine(DATABASE_URL, echo=SQLALCHEMY_ECHO)

# 4. Configurar la Fábrica de Sesiones
SessionLocal = sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False
)

# 5. Base para los Modelos (MVC)
# se hereda en cada modelo para definir las tablas y relaciones
Base = declarative_base()

# 6. Dependencia para FastAPI
# Esta función abre y cierra la conexión automáticamente en cada petición
async def get_db():
    async with SessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()