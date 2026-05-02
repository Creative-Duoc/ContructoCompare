from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import func
from sqlalchemy.orm import selectinload
from backend.app.database import get_db
from backend.app.models.inventory import ProductoMaestro, PrecioRetailer, Categoria, Retailer
from backend.app.schemas.inventory import (
    PrecioScraperCreate, 
    PrecioResponse, 
    ProductoConsolidadoResponse,
    TiendaPrecioResponse
)

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

@router.get("/all/productos", response_model=list[ProductoConsolidadoResponse])
async def obtener_todos_los_productos(db: AsyncSession = Depends(get_db)):
    """Retorna el catálogo completo con la última captura de precio agrupada por producto maestro."""
    
    # 1. Subconsulta para obtener la última fecha de captura por producto y retailer
    subq = (
        select(
            PrecioRetailer.id_producto_maestro,
            PrecioRetailer.id_retailer,
            func.max(PrecioRetailer.fecha_captura).label("ultima_captura"),
        )
        .group_by(PrecioRetailer.id_producto_maestro, PrecioRetailer.id_retailer)
        .subquery()
    )

    # 2. Query principal: Traemos los productos maestros con sus categorías
    query = (
        select(ProductoMaestro)
        .options(selectinload(ProductoMaestro.categoria))
        .order_by(ProductoMaestro.nombre_producto)
    )
    
    result = await db.execute(query)
    productos_maestros = result.scalars().all()

    # 3. Query para traer todos los precios "últimos" con sus retailers
    precios_query = (
        select(
            PrecioRetailer,
            Retailer.nombre_retailer
        )
        .join(Retailer, Retailer.id_retailer == PrecioRetailer.id_retailer)
        .join(
            subq,
            (subq.c.id_producto_maestro == PrecioRetailer.id_producto_maestro)
            & (subq.c.id_retailer == PrecioRetailer.id_retailer)
            & (subq.c.ultima_captura == PrecioRetailer.fecha_captura),
        )
    )
    
    precios_result = await db.execute(precios_query)
    todos_los_precios = precios_result.all()

    # 4. Agrupamos precios por id_producto_maestro
    precios_por_producto = {}
    for p_retail, r_name in todos_los_precios:
        pid = p_retail.id_producto_maestro
        if pid not in precios_por_producto:
            precios_por_producto[pid] = []
        
        precios_por_producto[pid].append(TiendaPrecioResponse(
            tienda=r_name,
            precio_clp=p_retail.precio_clp,
            disponibilidad=p_retail.disponibilidad,
            link_producto=p_retail.link_producto,
            fecha_captura=p_retail.fecha_captura
        ))

    # 5. Construimos la respuesta final consolidada
    respuesta = []
    for pm in productos_maestros:
        tiendas = precios_por_producto.get(pm.id_producto, [])
        if not tiendas:
            continue # Omitimos productos sin precios
            
        respuesta.append(ProductoConsolidadoResponse(
            id_producto=pm.id_producto,
            sku_maestro=pm.sku_maestro,
            nombre_producto=pm.nombre_producto,
            categoria=pm.categoria.nombre_categoria,
            foto_url=pm.foto_url,
            tiendas=tiendas
        ))

    return respuesta
