from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
from backend.app.database import Base

class TipoUsuario(Base):
    __tablename__ = "tipos_usuario"

    id_tipo = Column(Integer, primary_key=True, index=True)
    nombre_tipo = Column(String(50), unique=True, nullable=False)  # 'Persona Natural', 'Empresa', etc.
    descripcion = Column(String(255), nullable=True)

    usuarios = relationship("Usuario", back_populates="tipo")

class Usuario(Base):
    __tablename__ = "usuarios"

    id_usuario = Column(Integer, primary_key=True, index=True)
    nombre_completo = Column(String(150), nullable=False)
    correo_electronico = Column(String(150), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    id_tipo_usuario = Column(Integer, ForeignKey("tipos_usuario.id_tipo"), nullable=False)
    esta_activo = Column(Boolean, default=True)
    fecha_registro = Column(DateTime, default=datetime.utcnow)

    tipo = relationship("TipoUsuario", back_populates="usuarios")