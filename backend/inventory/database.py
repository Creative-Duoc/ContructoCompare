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

# Lógica para manejar parámetros incompatibles en asyncpg (como sslmode, channel_binding, etc.)
connect_args = {}
if "?" in DATABASE_URL:
    from urllib.parse import urlparse, parse_qs
    
    parsed = urlparse(DATABASE_URL)
    query = parse_qs(parsed.query)
    
    # Si detectamos que se solicita SSL, lo activamos en connect_args
    ssl_mode = query.get("sslmode", [""])[0]
    if ssl_mode in ("require", "prefer", "allow") or "sslmode" not in query:
        # Por defecto, si es una base de datos externa, solemos querer SSL
        # Si da problemas en local, se puede ajustar
        if "localhost" not in DATABASE_URL and "127.0.0.1" not in DATABASE_URL:
            connect_args["ssl"] = True
    
    # Limpiamos COMPLETAMENTE la URL de parámetros para evitar TypeErrors
    # asyncpg es muy estricto con los argumentos que recibe por URL
    DATABASE_URL = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"

SQLALCHEMY_ECHO = os.getenv("SQLALCHEMY_ECHO", "false").lower() in {"1", "true", "yes", "on"}

# 3. Crear el Motor Asíncrono
engine = create_async_engine(
    DATABASE_URL, 
    echo=SQLALCHEMY_ECHO,
    connect_args=connect_args,
    pool_recycle=3600,         # Refresca conexiones cada 1 hora
    pool_pre_ping=True,        # Verifica si la conexión está viva antes de usarla
    pool_size=5,               # Tamaño base del pool
    max_overflow=10            # Conexiones extra permitidas en picos de tráfico
)

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