from pydantic import BaseModel, Field, HttpUrl
from typing import Optional
from datetime import datetime
from decimal import Decimal

# --- Esquemas para recibir datos del Scraper 
class PrecioScraperCreate(BaseModel):
    sku_maestro: int = Field(..., description="Código interno para identificar el producto")
    id_retailer: int = Field(..., description="ID de la tienda (Sodimac, Easy, Imperial)")
    precio_clp: Decimal = Field(..., gt=0, decimal_places=2, description="Valor en pesos chilenos")
    disponibilidad: bool = Field(..., description="TRUE si hay stock, FALSE si está agotado")
    link_producto: HttpUrl = Field(..., description="URL directa para redireccionamiento")

# --- Esquemas de Respuesta para el Frontend 
class ProductoResponse(BaseModel):
    id_producto: int
    sku_maestro: int
    nombre_producto: str
    id_categoria: int

    class Config:
        from_attributes = True

class PrecioResponse(BaseModel):
    id_precio: int
    id_producto_maestro: int
    id_retailer: int
    precio_clp: Decimal
    precio_uf: Optional[Decimal]
    disponibilidad: bool
    fecha_captura: datetime

    class Config:
        from_attributes = True