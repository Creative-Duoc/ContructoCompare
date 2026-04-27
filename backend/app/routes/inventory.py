from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import func
from backend.app.database import get_db
from backend.app.models.inventory import ProductoMaestro, PrecioRetailer, Categoria, Retailer
from backend.app.schemas.inventory import PrecioScraperCreate, PrecioResponse, ProductoGeneralResponse

router = APIRouter(prefix="/api/v1/inventory", tags=["Inventory Engine"])

@router.get("/productos/{id_producto}/historial", response_model=list[PrecioResponse])
async def obtener_historial_precios(id_producto: int, db: AsyncSession = Depends(get_db)):
    query = (
        select(PrecioRetailer)
        .where(PrecioRetailer.id_producto_maestro == id_producto)
        .order_by(PrecioRetailer.fecha_captura.asc())
    )
    result = await db.execute(query)
    precios = result.scalars().all()
    return precios if precios else []

@router.post("/precios", response_model=PrecioResponse)
async def registrar_precio_scraper(data: PrecioScraperCreate, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(ProductoMaestro).where(ProductoMaestro.sku_maestro == data.sku_maestro))
    producto = result.scalars().first()
    
    if not producto:
        raise HTTPException(status_code=404, detail=f"El SKU Maestro {data.sku_maestro} no existe.")

    nuevo_precio = PrecioRetailer(
        id_producto_maestro=producto.id_producto,
        id_retailer=data.id_retailer,
        precio_clp=data.precio_clp,
        disponibilidad=data.disponibilidad,
        link_producto=str(data.link_producto),
    )
    
    db.add(nuevo_precio)
    await db.commit()
    await db.refresh(nuevo_precio)
    return nuevo_precio

@router.get("/all/productos", response_model=list[ProductoGeneralResponse])
async def obtener_todos_los_productos(db: AsyncSession = Depends(get_db)):
    """Retorna el catálogo completo con la última captura de precio por tienda."""
    
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
            ProductoMaestro.sku_maestro,
            ProductoMaestro.nombre_producto,
            Categoria.nombre_categoria.label("categoria"),
            Retailer.nombre_retailer.label("retailer"),
            PrecioRetailer.precio_clp,
            PrecioRetailer.disponibilidad,
            PrecioRetailer.link_producto,
            PrecioRetailer.fecha_captura,
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
        .order_by(ProductoMaestro.nombre_producto)
    )

    result = await db.execute(query)
    return result.mappings().all()
