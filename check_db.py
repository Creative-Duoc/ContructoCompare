import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from backend.inventory.database import SessionLocal
from backend.inventory.models.inventory import ProductoMaestro, PrecioRetailer, Retailer
from sqlalchemy.future import select
from sqlalchemy import func


async def check():
    async with SessionLocal() as s:
        pm = (await s.execute(select(func.count()).select_from(ProductoMaestro))).scalar()
        pr = (await s.execute(select(func.count()).select_from(PrecioRetailer))).scalar()
        rows = (await s.execute(
            select(Retailer.nombre_retailer, func.count(PrecioRetailer.id_precio))
            .join(Retailer, Retailer.id_retailer == PrecioRetailer.id_retailer)
            .group_by(Retailer.nombre_retailer)
        )).all()
        print(f"ProductoMaestro total: {pm}")
        print(f"PrecioRetailer total:  {pr}")
        for nombre, cnt in rows:
            print(f"  {nombre}: {cnt} registros de precio")


asyncio.run(check())
