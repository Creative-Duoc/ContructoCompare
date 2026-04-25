import os
from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, declarative_base

# 1. Cargar variables de entorno (para seguridad de credenciales)
load_dotenv()

# 2. Configurar la URL de conexión
DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:

    DATABASE_URL = "postgresql+asyncpg://postgres:tu_password@localhost:5432/constructo_db"

# 3. Crear el Motor Asíncrono
# echo=True permite ver las consultas SQL en la terminal 
engine = create_async_engine(DATABASE_URL, echo=True)

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