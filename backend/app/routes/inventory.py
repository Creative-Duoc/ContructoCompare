from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import func
from backend.app.database import get_db

# Importamos los Modelos (Base de datos)
from backend.app.models.inventory import ProductoMaestro, PrecioRetailer, Categoria, Retailer

# Importamos los Esquemas
from backend.app.schemas.inventory import PrecioScraperCreate, PrecioResponse, ProductoResponse, ProductoSodimacResponse

NOMBRE_RETAILER_SODIMAC = "Sodimac"

router = APIRouter(prefix="/api/v1/inventory", tags=["Inventory Engine"])

@router.post("/precios", response_model=PrecioResponse)
async def registrar_precio_scraper(data: PrecioScraperCreate, db: AsyncSession = Depends(get_db)):
    # 1. QA / Regla de Negocio: Verificar que el producto maestro exista
    result = await db.execute(select(ProductoMaestro).where(ProductoMaestro.sku_maestro == data.sku_maestro))
    producto = result.scalars().first()
    
    if not producto:
        raise HTTPException(status_code=404, detail=f"El SKU Maestro {data.sku_maestro} no existe en el catálogo.")

    # 2. Crear el registro en PRECIO_RETAILER
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


@router.get("/productos", response_model=list[ProductoResponse])
async def obtener_catalogo_maestro(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(ProductoMaestro))
    return result.scalars().all()


@router.get("/sodimac/productos", response_model=list[ProductoSodimacResponse])
async def obtener_productos_sodimac(db: AsyncSession = Depends(get_db)):
    # Obtener el id del retailer Sodimac
    retailer_result = await db.execute(
        select(Retailer).where(func.lower(Retailer.nombre_retailer) == NOMBRE_RETAILER_SODIMAC.lower())
    )
    retailer = retailer_result.scalars().first()
    if not retailer:
        raise HTTPException(status_code=404, detail="Retailer Sodimac no encontrado en la base de datos.")

    # Subconsulta: precio más reciente por producto en Sodimac
    subq = (
        select(
            PrecioRetailer.id_producto_maestro,
            func.max(PrecioRetailer.fecha_captura).label("ultima_captura"),
        )
        .where(PrecioRetailer.id_retailer == retailer.id_retailer)
        .group_by(PrecioRetailer.id_producto_maestro)
        .subquery()
    )

    # JOIN para traer producto + precio más reciente
    query = (
        select(
            ProductoMaestro.id_producto,
            ProductoMaestro.sku_maestro,
            ProductoMaestro.nombre_producto,
            Categoria.nombre_categoria.label("categoria"),
            PrecioRetailer.precio_clp,
            PrecioRetailer.disponibilidad,
            PrecioRetailer.link_producto,
            PrecioRetailer.fecha_captura,
        )
        .join(PrecioRetailer, PrecioRetailer.id_producto_maestro == ProductoMaestro.id_producto)
        .join(Categoria, Categoria.id_categoria == ProductoMaestro.id_categoria)
        .join(
            subq,
            (subq.c.id_producto_maestro == PrecioRetailer.id_producto_maestro)
            & (subq.c.ultima_captura == PrecioRetailer.fecha_captura),
        )
        .where(PrecioRetailer.id_retailer == retailer.id_retailer)
        .order_by(ProductoMaestro.nombre_producto)
    )

    result = await db.execute(query)
    rows = result.mappings().all()
    return [ProductoSodimacResponse(**row) for row in rows]