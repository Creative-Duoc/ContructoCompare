from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from app.database import get_db

# Importamos los Modelos (Base de datos)
from app.models.inventory import ProductoMaestro, PrecioRetailer

# Importamos los Esquemas 
from app.schemas.inventory import PrecioScraperCreate, PrecioResponse, ProductoResponse

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