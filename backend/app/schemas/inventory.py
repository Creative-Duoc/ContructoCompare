from pydantic import BaseModel, Field, HttpUrl
from typing import Optional, List
from datetime import datetime
from decimal import Decimal

# --- Esquemas para recibir datos del Scraper 
class PrecioScraperCreate(BaseModel):
    id_producto_maestro: int = Field(..., description="ID del producto en el catálogo maestro")
    id_retailer: int = Field(..., description="ID de la tienda (Sodimac, Easy, Imperial)")
    sku_tienda: str = Field(..., description="Código del producto en la tienda específica")
    precio_clp: Decimal = Field(..., gt=0, decimal_places=2, description="Valor en pesos chilenos")
    disponibilidad: bool = Field(..., description="TRUE si hay stock, FALSE si está agotado")
    link_producto: HttpUrl = Field(..., description="URL directa para redireccionamiento")

# --- Esquemas de Respuesta para el Frontend 
class PrecioResponse(BaseModel):
    id_precio: int
    id_producto_maestro: int
    id_retailer: int
    sku_tienda: Optional[str]
    precio_clp: Decimal
    precio_uf: Optional[Decimal]
    disponibilidad: bool
    fecha_captura: datetime

    class Config:
        from_attributes = True

class UnidadMedidaResponse(BaseModel):
    id_unidad: int
    nombre_unidad: str
    abreviatura: str
    tipo_magnitud: str

    class Config:
        from_attributes = True

class ProductoGeneralResponse(BaseModel):
    id_producto: int
    nombre_producto: str
    foto_url: str
    marca: Optional[str]
    categoria: str
    retailer: str
    sku_tienda: str
    precio_clp: Decimal
    disponibilidad: bool
    link_producto: str
    fecha_captura: datetime
    # Nuevos campos de medida
    unidad: Optional[str]
    abreviatura_unidad: Optional[str]
    valor_medida: Optional[Decimal]

    class Config:
        from_attributes = True

# --- Esquemas para Cotizaciones ---

class DetalleCotizacionCreate(BaseModel):
    id_producto_maestro: int
    id_retailer: int
    cantidad: int = 1

class DetalleCotizacionResponse(BaseModel):
    id_detalle: int
    id_producto_maestro: int
    id_retailer: int
    cantidad: int

    class Config:
        from_attributes = True

class CotizacionCreate(BaseModel):
    nombre_proyecto: str
    detalles: List[DetalleCotizacionCreate]

class CotizacionResponse(BaseModel):
    id_cotizacion: int
    id_usuario: int
    nombre_proyecto: str
    fecha_creacion: datetime
    estado: str
    detalles: List[DetalleCotizacionResponse]

    class Config:
        from_attributes = True
    class Config:
        from_attributes = True

class TiendaPrecioResponse(BaseModel):
    tienda: str
    precio_clp: Decimal
    disponibilidad: bool
    link_producto: str
    fecha_captura: datetime

class ProductoConsolidadoResponse(BaseModel):
    id_producto: int
    sku_maestro: int
    nombre_producto: str
    categoria: str
    foto_url: Optional[str] = None
    tiendas: List[TiendaPrecioResponse]

    class Config:
        from_attributes = True
