from fastapi import FastAPI
from app.routes import inventory
from app.routes import inventory, users
from app.database import engine, Base
import asyncio

app = FastAPI(title="ConstructoCompare - Inventory Service")

# Crear las tablas en la DB al arrancar (solo para desarrollo)
async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

@app.on_event("startup")
async def startup():
    await init_db()

# Incluir las rutas del controlador
app.include_router(inventory.router)
app.include_router(users.router) # Se añade el nuevo router de usuarios

@app.get("/")
async def root():
    return {"message": "Inventory Service Online",
        "modules": ["Inventory", "Users"],
        "docs": "/docs"
    }