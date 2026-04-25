import os
import sys
from pathlib import Path

# Allow running from backend/app with: python .\\main.py
if __package__ in {None, ""}:
    project_root = Path(__file__).resolve().parents[2]
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))

from fastapi import FastAPI

from backend.app.database import Base, engine
from backend.app.routes import inventory, users

app = FastAPI(title="ConstructoCompare - Inventory Service")
AUTO_CREATE_TABLES = os.getenv("AUTO_CREATE_TABLES", "true").lower() in {"1", "true", "yes", "on"}


async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


@app.on_event("startup")
async def startup():
    if AUTO_CREATE_TABLES:
        await init_db()


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

    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=False)
