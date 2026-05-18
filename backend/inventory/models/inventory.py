from sqlalchemy import Column, Integer, String, Numeric, Boolean, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from backend.inventory.database import Base
import datetime

class Categoria(Base):
    __tablename__ = "categoria"
    id_categoria = Column(Integer, primary_key=True, index=True)
    nombre_categoria = Column(String(100), nullable=False, unique=True)
    
    productos = relationship("ProductoMaestro", back_populates="categoria")

class Marca(Base):
    __tablename__ = "marca"
    id_marca = Column(Integer, primary_key=True, index=True)
    nombre_marca = Column(String(100), nullable=False, unique=True)

    productos = relationship("ProductoMaestro", back_populates="marca")

class UnidadMedida(Base):
    __tablename__ = "unidad_medida"
    id_unidad = Column(Integer, primary_key=True, index=True)
    nombre_unidad = Column(String(50), nullable=False)
    abreviatura = Column(String(10), nullable=False)
    tipo_magnitud = Column(String(20), nullable=False) # 'Masa', 'Volumen', etc.

    productos = relationship("ProductoMaestro", back_populates="unidad")

class Retailer(Base):
    __tablename__ = "retailer"
    id_retailer = Column(Integer, primary_key=True, index=True)
    nombre_retailer = Column(String(100), nullable=False, unique=True)
    url_base = Column(String(100), nullable=False)
    logo_path = Column(String(100), nullable=False)

    precios = relationship("PrecioRetailer", back_populates="retailer")

class ProductoMaestro(Base):
    __tablename__ = "producto_maestro"
    id_producto = Column(Integer, primary_key=True, index=True)
    nombre_producto = Column(String(255), nullable=False) 
    foto_url = Column(String, nullable=True)
    id_categoria = Column(Integer, ForeignKey("categoria.id_categoria"), nullable=False)
    id_marca = Column(Integer, ForeignKey("marca.id_marca"), nullable=True)
    id_unidad = Column(Integer, ForeignKey("unidad_medida.id_unidad"), nullable=True)
    valor_medida = Column(Numeric(10, 2), nullable=True) # Ej: 25.0
    
    categoria = relationship("Categoria", back_populates="productos")
    marca = relationship("Marca", back_populates="productos")
    unidad = relationship("UnidadMedida", back_populates="productos")
    precios = relationship("PrecioRetailer", back_populates="producto")

class PrecioRetailer(Base):
    __tablename__ = "precio_retailer"
    id_precio = Column(Integer, primary_key=True, index=True)
    id_producto_maestro = Column(Integer, ForeignKey("producto_maestro.id_producto"), nullable=False)
    id_retailer = Column(Integer, ForeignKey("retailer.id_retailer"), nullable=False)
    sku_tienda = Column(String(100), nullable=False) 
    precio_clp = Column(Numeric(12, 2), nullable=False)
    precio_uf = Column(Numeric(12, 5), nullable=True)
    disponibilidad = Column(Boolean, nullable=False, default=True)
    link_producto = Column(String, nullable=False)
    fecha_captura = Column(DateTime(timezone=True), default=datetime.datetime.utcnow, nullable=False)

    producto = relationship("ProductoMaestro", back_populates="precios")
    retailer = relationship("Retailer", back_populates="precios")

class Cotizacion(Base):
    __tablename__ = "cotizacion"
    id_cotizacion = Column(Integer, primary_key=True, index=True)
    id_usuario = Column(Integer, ForeignKey("usuarios.id_usuario"), nullable=False)
    nombre_proyecto = Column(String(255), nullable=False)
    fecha_creacion = Column(DateTime(timezone=True), default=datetime.datetime.utcnow)
    estado = Column(String(50), default="Borrador")

    detalles = relationship(
        "DetalleCotizacion",
        back_populates="cotizacion",
        cascade="all, delete-orphan",
    )

class DetalleCotizacion(Base):
    __tablename__ = "detalle_cotizacion"
    id_detalle = Column(Integer, primary_key=True, index=True)
    id_cotizacion = Column(Integer, ForeignKey("cotizacion.id_cotizacion"), nullable=False)
    id_producto_maestro = Column(Integer, ForeignKey("producto_maestro.id_producto"), nullable=False)
    id_retailer = Column(Integer, ForeignKey("retailer.id_retailer"), nullable=False)
    cantidad = Column(Integer, nullable=False, default=1)

    cotizacion = relationship("Cotizacion", back_populates="detalles")