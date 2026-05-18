from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import func
<<<<<<< HEAD:backend/app/routes/inventory.py
from app.database import get_db

# Importamos los Modelos (Base de datos)
from app.models.inventory import ProductoMaestro, PrecioRetailer, Categoria, Retailer

# Importamos los Esquemas
from app.schemas.inventory import PrecioScraperCreate, PrecioResponse, ProductoResponse, ProductoSodimacResponse

NOMBRE_RETAILER_SODIMAC = "Sodimac"
=======
from backend.inventory.database import get_db
from backend.inventory.models.inventory import ProductoMaestro, PrecioRetailer, Categoria, Retailer, Marca, UnidadMedida
from backend.inventory.schemas.inventory import (
    PrecioScraperCreate, 
    PrecioResponse, 
    ProductoGeneralResponse,
)
>>>>>>> 02f376ae7a42795309f8148eef863ffcd16e4f4d:backend/inventory/routes/inventory.py

router = APIRouter(prefix="/api/v1/inventory", tags=["Inventory Engine"])

# --- Endpoints de Productos ---

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
    result = await db.execute(select(ProductoMaestro).where(ProductoMaestro.id_producto == data.id_producto_maestro))
    producto = result.scalars().first()
    
    if not producto:
        raise HTTPException(status_code=404, detail=f"El ID Producto Maestro {data.id_producto_maestro} no existe.")

    nuevo_precio = PrecioRetailer(
        id_producto_maestro=producto.id_producto,
        id_retailer=data.id_retailer,
        sku_tienda=data.sku_tienda,
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
    """Retorna el catálogo completo con la última captura de precio por tienda e información de medida."""
    
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
            ProductoMaestro.nombre_producto,
            ProductoMaestro.foto_url,
            Marca.nombre_marca.label("marca"),
            Categoria.nombre_categoria.label("categoria"),
            Retailer.nombre_retailer.label("retailer"),
            PrecioRetailer.sku_tienda,
            PrecioRetailer.precio_clp,
            PrecioRetailer.disponibilidad,
            PrecioRetailer.link_producto,
            PrecioRetailer.fecha_captura,
            UnidadMedida.nombre_unidad.label("unidad"),
            UnidadMedida.abreviatura.label("abreviatura_unidad"),
            ProductoMaestro.valor_medida
        )
        .join(PrecioRetailer, PrecioRetailer.id_producto_maestro == ProductoMaestro.id_producto)
        .join(Categoria, Categoria.id_categoria == ProductoMaestro.id_categoria)
        .outerjoin(Marca, Marca.id_marca == ProductoMaestro.id_marca)
        .outerjoin(UnidadMedida, UnidadMedida.id_unidad == ProductoMaestro.id_unidad)
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
