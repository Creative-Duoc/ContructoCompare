import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from backend.inventory.database import SessionLocal
from backend.inventory.models.inventory import PrecioRetailer, Retailer
from sqlalchemy.future import select


async def check():
    bronze_path = Path("scrapers/data/bronze/sodimac_products.json")
    data = json.loads(bronze_path.read_text(encoding="utf-8"))
    bronze_urls = [p["product_url"] for p in data["products"][:5] if p.get("product_url")]

    async with SessionLocal() as s:
        res = await s.execute(
            select(Retailer).where(Retailer.nombre_retailer == "Sodimac")
        )
        retailer = res.scalars().first()

        res2 = await s.execute(
            select(PrecioRetailer.link_producto)
            .where(PrecioRetailer.id_retailer == retailer.id_retailer)
            .limit(5)
        )
        db_urls = [r[0] for r in res2.all()]

    print("=== URLs en Bronze (primeras 5) ===")
    for u in bronze_urls:
        print(" ", u)

    print("\n=== URLs en BD PrecioRetailer (primeras 5) ===")
    for u in db_urls:
        print(" ", u)


asyncio.run(check())
