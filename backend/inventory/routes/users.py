from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from backend.inventory.database import get_db
from backend.inventory.models.inventory import Cotizacion, DetalleCotizacion
from backend.inventory.models.users import Usuario
from backend.inventory.schemas.users import PasswordUpdate, TokenResponse, UsuarioCreate, UsuarioLogin, UsuarioResponse,UsuarioUpdate
from backend.inventory.security import (
    ALGORITHM,
    SECRET_KEY,
    create_access_token,
    get_password_hash,
    needs_rehash,
    verify_password,
)

router = APIRouter(prefix="/api/v1/users", tags=["User Management"])
security = HTTPBearer()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db),
) -> Usuario:
    token = credentials.credentials
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
    return TokenResponse(
    access_token=access_token,
    token_type="bearer"
)

@router.get("/me", response_model=UsuarioResponse)
async def obtener_mi_usuario(usuario_actual: Usuario = Depends(get_current_user)):
    return usuario_actual


@router.put("/password", status_code=status.HTTP_200_OK)
async def cambiar_password(
    datos: PasswordUpdate,
    usuario_actual: Usuario = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if not verify_password(datos.contrasena_actual, usuario_actual.password_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="La contraseña actual es incorrecta.",
        )

    usuario_actual.password_hash = get_password_hash(datos.nueva_contrasena)
    db.add(usuario_actual)
    await db.commit()
    return {"message": "Contraseña actualizada exitosamente."}


@router.delete("/me", status_code=status.HTTP_200_OK)
async def eliminar_cuenta(
    usuario_actual: Usuario = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    subq = select(Cotizacion.id_cotizacion).where(Cotizacion.id_usuario == usuario_actual.id_usuario)
    await db.execute(delete(DetalleCotizacion).where(DetalleCotizacion.id_cotizacion.in_(subq)))
    await db.execute(delete(Cotizacion).where(Cotizacion.id_usuario == usuario_actual.id_usuario))
    await db.delete(usuario_actual)
    await db.commit()
    return {"message": "Cuenta eliminada exitosamente."}

@router.put("/profile", response_model=UsuarioResponse)
async def actualizar_perfil(
    datos: UsuarioUpdate,
    usuario_actual: Usuario = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # 1. Verificar si el nuevo correo ya está tomado por otro usuario
    if datos.correo_electronico != usuario_actual.correo_electronico:
        query = select(Usuario).where(Usuario.correo_electronico == datos.correo_electronico)
        result = await db.execute(query)
        usuario_existente = result.scalars().first()
        
        if usuario_existente:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="El nuevo correo electrónico ya está registrado."
            )

    # 2. Actualizar los campos
    usuario_actual.nombre_completo = datos.nombre_completo
    usuario_actual.correo_electronico = datos.correo_electronico

    # 3. Persistir cambios
    db.add(usuario_actual)
    await db.commit()
    await db.refresh(usuario_actual)
    
    return usuario_actual