from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import func
from sqlalchemy.orm import selectinload
from backend.app.database import get_db
from backend.app.models.inventory import ProductoMaestro, PrecioRetailer, Categoria, Retailer, Marca, UnidadMedida, Cotizacion, DetalleCotizacion
from backend.app.schemas.inventory import (
    PrecioScraperCreate, 
    PrecioResponse, 
    ProductoGeneralResponse,
    CotizacionCreate,
    CotizacionResponse
)
from backend.app.routes.users import get_current_user
from backend.app.models.users import Usuario

router = APIRouter(prefix="/api/v1/inventory", tags=["Inventory Engine"])

# --- Endpoints de Cotizaciones ---

@router.post("/cotizaciones", response_model=CotizacionResponse)
async def crear_cotizacion(
    data: CotizacionCreate, 
    db: AsyncSession = Depends(get_db),
    usuario_actual: Usuario = Depends(get_current_user)
):
    nueva_cotizacion = Cotizacion(
        id_usuario=usuario_actual.id_usuario,
        nombre_proyecto=data.nombre_proyecto
    )
    db.add(nueva_cotizacion)
    await db.flush() # Para obtener id_cotizacion

    for det in data.detalles:
        nuevo_detalle = DetalleCotizacion(
            id_cotizacion=nueva_cotizacion.id_cotizacion,
            id_producto_maestro=det.id_producto_maestro,
            id_retailer=det.id_retailer,
            cantidad=det.cantidad
        )
        db.add(nuevo_detalle)
    
    await db.commit()
    await db.refresh(nueva_cotizacion)
    return nueva_cotizacion

@router.get("/cotizaciones", response_model=list[CotizacionResponse])
async def listar_mis_cotizaciones(
    db: AsyncSession = Depends(get_db),
    usuario_actual: Usuario = Depends(get_current_user)
):
    query = select(Cotizacion).where(Cotizacion.id_usuario == usuario_actual.id_usuario).options(selectinload(Cotizacion.detalles))
    result = await db.execute(query)
    return result.scalars().all()

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
