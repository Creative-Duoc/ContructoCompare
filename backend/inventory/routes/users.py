from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
<<<<<<< HEAD:backend/app/routes/users.py
from app.database import get_db
from app.models.users import Usuario
from app.schemas.users import TokenResponse, UsuarioCreate, UsuarioLogin, UsuarioResponse
from app.security import (
=======
from backend.inventory.database import get_db
from backend.inventory.models.users import Usuario
from backend.inventory.schemas.users import TokenResponse, UsuarioCreate, UsuarioLogin, UsuarioResponse
from backend.inventory.security import (
>>>>>>> 02f376ae7a42795309f8148eef863ffcd16e4f4d:backend/inventory/routes/users.py
    ALGORITHM,
    SECRET_KEY,
    create_access_token,
    get_password_hash,
    needs_rehash,
    verify_password,
)

router = APIRouter(prefix="/api/v1/users", tags=["User Management"])
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/users/login")


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> Usuario:
    credenciales_invalidas = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="No se pudo validar el token.",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        subject = payload.get("sub")
        if subject is None:
            raise credenciales_invalidas
        user_id = int(subject)
    except (JWTError, ValueError):
        raise credenciales_invalidas

    result = await db.execute(select(Usuario).where(Usuario.id_usuario == user_id))
    usuario_actual = result.scalars().first()

    if not usuario_actual:
        raise HTTPException(status_code=404, detail="Usuario no encontrado.")

    return usuario_actual

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
        password_hash=get_password_hash(user_data.password),
        id_tipo_usuario=user_data.id_tipo_usuario,
    )

    db.add(nuevo_usuario)
    await db.commit()
    await db.refresh(nuevo_usuario)
    
    return nuevo_usuario

@router.post("/login", response_model=TokenResponse)
async def login_usuario(user_data: UsuarioLogin, db: AsyncSession = Depends(get_db)):
    query = select(Usuario).where(Usuario.correo_electronico == user_data.correo_electronico)
    result = await db.execute(query)
    usuario = result.scalars().first()

    if not usuario or not verify_password(user_data.password, usuario.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciales invalidas.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Si el usuario viene de datos legacy en texto plano, se sanea al primer login.
    if needs_rehash(usuario.password_hash):
        usuario.password_hash = get_password_hash(user_data.password)
        db.add(usuario)
        await db.commit()

    access_token = create_access_token(subject=str(usuario.id_usuario))
    return TokenResponse(access_token=access_token)


@router.get("/me", response_model=UsuarioResponse)
async def obtener_mi_usuario(usuario_actual: Usuario = Depends(get_current_user)):
    return usuario_actual