import asyncio
import sys
from pathlib import Path

# Configurar path para importar backend
ROOT_DIR = Path(__file__).resolve().parent
sys.path.append(str(ROOT_DIR))

from sqlalchemy.future import select
from sqlalchemy import func
from backend.app.database import SessionLocal
from backend.app.models.inventory import ProductoMaestro, PrecioRetailer, Categoria, Retailer

async def debug():
    print("--- DEBUG DB ---")
    async with SessionLocal() as session:
        # Contar base
        res_p = await session.execute(select(func.count(ProductoMaestro.id_producto)))
        print(f"Total Productos Maestros: {res_p.scalar()}")
        
        res_r = await session.execute(select(func.count(Retailer.id_retailer)))
        print(f"Total Retailers: {res_r.scalar()}")
        
        res_c = await session.execute(select(func.count(Categoria.id_categoria)))
        print(f"Total Categorias: {res_c.scalar()}")
        
        res_pr = await session.execute(select(func.count(PrecioRetailer.id_precio)))
        print(f"Total Precios: {res_pr.scalar()}")

        # Probar el query exacto del endpoint
        subq = (
            select(
                PrecioRetailer.id_producto_maestro,
                PrecioRetailer.id_retailer,
                func.max(PrecioRetailer.fecha_captura).label("ultima_captura"),
            )
            .group_by(PrecioRetailer.id_producto_maestro, PrecioRetailer.id_retailer)
            .subquery()
        )

        query = (
            select(
                ProductoMaestro.id_producto,
                Retailer.nombre_retailer,
                PrecioRetailer.precio_clp,
            )
            .join(PrecioRetailer, PrecioRetailer.id_producto_maestro == ProductoMaestro.id_producto)
            .join(Categoria, Categoria.id_categoria == ProductoMaestro.id_categoria)
            .join(Retailer, Retailer.id_retailer == PrecioRetailer.id_retailer)
            .join(
                subq,
                (subq.c.id_producto_maestro == PrecioRetailer.id_producto_maestro)
                & (subq.c.id_retailer == PrecioRetailer.id_retailer)
                & (subq.c.ultima_captura == PrecioRetailer.fecha_captura),
            )
        )
        
        res_all = await session.execute(query)
        rows = res_all.all()
        print(f"Productos que pasarían el Join del endpoint: {len(rows)}")
        
        if len(rows) > 0:
            print("Ejemplo de primer producto:")
            print(rows[0])
        else:
            print("ALERTA: El JOIN no está devolviendo nada. Verificando integridad...")
            # Ver si hay productos sin categoría o precios sin retailer
            p_sin_cat = await session.execute(select(ProductoMaestro).where(ProductoMaestro.id_categoria == None))
            print(f"Productos sin categoria: {len(p_sin_cat.all())}")

if __name__ == "__main__":
    asyncio.run(debug())
