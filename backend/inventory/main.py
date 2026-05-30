import os
import sys
from pathlib import Path

# Allow running from backend/inventory with: python main.py
if __package__ in {None, ""}:
    project_root = Path(__file__).resolve().parents[2]
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from backend.inventory.database import Base, engine, SessionLocal
from backend.inventory.routes import inventory, users
from backend.inventory.models.users import TipoUsuario
from backend.inventory.models.inventory import Retailer, UnidadMedida

app = FastAPI(title="ConstructoCompare - Inventory Service")
AUTO_CREATE_TABLES = os.getenv("AUTO_CREATE_TABLES", "true").lower() in {"1", "true", "yes", "on"}

limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

CORS_ORIGINS_RAW = os.getenv("CORS_ORIGINS", "http://localhost:3000,http://localhost:5173,http://127.0.0.1:3000,http://127.0.0.1:5173")
CORS_ORIGINS = [origin.strip() for origin in CORS_ORIGINS_RAW.split(",") if origin.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

async def seed_data():
    """Puebla automáticamente las tablas maestras (Tipos de Cuenta, Retailers y Unidades)."""
    async with SessionLocal() as session:
        async with session.begin():
            # 1. Tipos de Usuario
            tipos = [
                TipoUsuario(id_tipo=1, nombre_tipo="Particular", descripcion="Persona natural"),
                TipoUsuario(id_tipo=2, nombre_tipo="Profesional", descripcion="Maestro o contratista independiente"),
                TipoUsuario(id_tipo=3, nombre_tipo="Empresa", descripcion="Empresa constructora o Pyme"),
            ]
            for t in tipos:
                await session.merge(t)

            # 2. Retailers
            retailers = [
                Retailer(id_retailer=1, nombre_retailer="Sodimac", url_base="https://www.sodimac.cl", logo_path="logos/sodimac.png"),
                Retailer(id_retailer=2, nombre_retailer="Easy", url_base="https://www.easy.cl", logo_path="logos/easy.png"),
                Retailer(id_retailer=3, nombre_retailer="Imperial", url_base="https://www.imperial.cl", logo_path="logos/imperial.png"),
            ]
            for r in retailers:
                await session.merge(r)

            # 3. Unidades de Medida
            unidades = [
                UnidadMedida(id_unidad=1, nombre_unidad="Kilogramo", abreviatura="kg", tipo_magnitud="Masa"),
                UnidadMedida(id_unidad=2, nombre_unidad="Metro", abreviatura="m", tipo_magnitud="Longitud"),
                UnidadMedida(id_unidad=3, nombre_unidad="Litro", abreviatura="lt", tipo_magnitud="Volumen"),
                UnidadMedida(id_unidad=4, nombre_unidad="Unidad", abreviatura="un", tipo_magnitud="Conteo"),
                UnidadMedida(id_unidad=5, nombre_unidad="Metro Cuadrado", abreviatura="m2", tipo_magnitud="Superficie"),
            ]
            for u in unidades:
                await session.merge(u)


@app.on_event("startup")
async def startup():
    if AUTO_CREATE_TABLES:
        await init_db()
        await seed_data()


app.include_router(inventory.router)
app.include_router(users.router)


@app.get("/")
async def root():
    return {
        "message": "Inventory Service Online",
        "modules": ["Inventory", "Users"],
        "docs": "/docs",
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="127.0.0.1", port=8001, reload=False)
