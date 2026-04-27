from sqlalchemy import Column, Integer, String, Numeric, Boolean, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from backend.app.database import Base
import datetime

class Categoria(Base):
    __tablename__ = "categoria"
    id_categoria = Column(Integer, primary_key=True, index=True) # Identificador único autoincremental
    nombre_categoria = Column(String(100), nullable=False) # Nombre descriptivo 
    
    productos = relationship("ProductoMaestro", back_populates="categoria")

class UnidadMedida(Base):
    __tablename__ = "unidad_medida"
    id_unidad = Column(Integer, primary_key=True, index=True) # Identificador único autoincremental de la unidad 
    nombre_unidad = Column(String(50), nullable=False) # Nombre completo 
    abreviatura = Column(String(10), nullable=False) # Sigla técnica 
    tipo_magnitud = Column(String(20), nullable=False) # Categoría: 'Masa', 'Volumen', etc 

class Retailer(Base):
    __tablename__ = "retailer"
    id_retailer = Column(Integer, primary_key=True, index=True) # Identificador único de la tienda de origen 
    nombre_retailer = Column(String(100), nullable=False) # Nombre comercial de la cadena de retail 
    url_base = Column(String(100), nullable=False) # URL base de la tienda 
    logo_path = Column(String(100), nullable=False) # Ruta al logo de la tienda 

class ProductoMaestro(Base):
    __tablename__ = "producto_maestro"
    id_producto = Column(Integer, primary_key=True, index=True) # Identificador maestro del producto 
    sku_maestro = Column(Integer, nullable=False, unique=True) # Código interno 
    nombre_producto = Column(String(255), nullable=False) # Nombre genérico estandarizado 
    id_categoria = Column(Integer, ForeignKey("categoria.id_categoria"), nullable=False) # Referencia a CATEGORIA 
    
    categoria = relationship("Categoria", back_populates="productos")
    precios = relationship("PrecioRetailer", back_populates="producto")

class PrecioRetailer(Base):
    __tablename__ = "precio_retailer"
    id_precio = Column(Integer, primary_key=True, index=True) # Registro individual de cada captura de precio
    id_producto_maestro = Column(Integer, ForeignKey("producto_maestro.id_producto"), nullable=False) # Vínculo con el catálogo maestro 
    id_retailer = Column(Integer, ForeignKey("retailer.id_retailer"), nullable=False) # ID de la tienda 
    precio_clp = Column(Numeric(12, 2), nullable=False) # Valor en pesos chilenos 
    precio_uf = Column(Numeric(12, 5), nullable=True) # Conversión calculada 
    disponibilidad = Column(Boolean, nullable=False) # TRUE si hay stock, FALSE si está agotado 
    link_producto = Column(String, nullable=False) # URL directa 
    fecha_captura = Column(DateTime(timezone=True), default=datetime.datetime.utcnow, nullable=False) # Marca temporal exacta 

    producto = relationship("ProductoMaestro", back_populates="precios")