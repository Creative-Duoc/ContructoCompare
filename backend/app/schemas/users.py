from pydantic import BaseModel, EmailStr, field_validator
from datetime import datetime

# Lo que recibimos del cliente para crear un nuevo usuario
class UsuarioCreate(BaseModel):
    nombre_completo: str
    correo_electronico: EmailStr
    password: str

    @field_validator("password")
    @classmethod
    def validar_password_seguro(cls, value: str) -> str:
        if len(value) < 8:
            raise ValueError("La contraseña debe tener al menos 8 caracteres.")
        if not any(char.isalpha() for char in value):
            raise ValueError("La contraseña debe incluir al menos una letra.")
        if not any(char.isdigit() for char in value):
            raise ValueError("La contraseña debe incluir al menos un numero.")
        return value


class UsuarioLogin(BaseModel):
    correo_electronico: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"

# para lo que devolvemos al cliente (sin el password)
class UsuarioResponse(BaseModel):
    id_usuario: int
    nombre_completo: str
    correo_electronico: EmailStr
    esta_activo: bool
    fecha_registro: datetime

    class Config:
        from_attributes = True