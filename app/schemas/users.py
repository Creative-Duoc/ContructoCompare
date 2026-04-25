from pydantic import BaseModel, EmailStr
from datetime import datetime
from typing import Optional

# Lo que recibimos del cliente para crear un nuevo usuario
class UsuarioCreate(BaseModel):
    nombre_completo: str
    correo_electronico: EmailStr
    password: str

# para lo que devolvemos al cliente (sin el password)
class UsuarioResponse(BaseModel):
    id_usuario: int
    nombre_completo: str
    correo_electronico: EmailStr
    esta_activo: bool
    fecha_registro: datetime

    class Config:
        from_attributes = True