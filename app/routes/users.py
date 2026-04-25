from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from app.database import get_db
from app.models.users import Usuario
from app.schemas.users import UsuarioCreate, UsuarioResponse

router = APIRouter(prefix="/api/v1/users", tags=["User Management"])

@router.post("/register", response_model=UsuarioResponse)
async def registrar_usuario(user_data: UsuarioCreate, db: AsyncSession = Depends(get_db)):
    # 1. QA / Regla de Negocio: Verificar que el correo no esté registrado
    query = select(Usuario).where(Usuario.correo_electronico == user_data.correo_electronico)
    result = await db.execute(query)
    user_existente = result.scalars().first()
    
    if user_existente:
        raise HTTPException(status_code=400, detail="Este correo ya está registrado en ConstructoCompare.")

    # 2. Crear el nuevo usuario 
    nuevo_usuario = Usuario(
        nombre_completo=user_data.nombre_completo,
        correo_electronico=user_data.correo_electronico,
        password_hash=user_data.password 
    )

    db.add(nuevo_usuario)
    await db.commit()
    await db.refresh(nuevo_usuario)
    
    return nuevo_usuario

@router.get("/me", response_model=list[UsuarioResponse])
async def listar_usuarios(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Usuario))
    return result.scalars().all()