from fastapi import APIRouter, Depends, HTTPException, Response, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

from backend.inventory.database import get_db
from backend.inventory.models.inventory import Cotizacion, DetalleCotizacion
from backend.inventory.models.users import Usuario
from backend.inventory.schemas.inventory import CotizacionCreate, CotizacionResponse, CotizacionUpdate
from backend.inventory.security import ALGORITHM, SECRET_KEY

router = APIRouter(prefix="/api/v1/cotizaciones", tags=["Quotes"])

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


async def _get_user_cotizacion(
    cotizacion_id: int,
    usuario_actual: Usuario,
    db: AsyncSession,
) -> Cotizacion:
    query = (
        select(Cotizacion)
        .where(
            Cotizacion.id_cotizacion == cotizacion_id,
            Cotizacion.id_usuario == usuario_actual.id_usuario,
        )
        .options(selectinload(Cotizacion.detalles))
    )
    result = await db.execute(query)
    cotizacion = result.scalars().first()
    if not cotizacion:
        raise HTTPException(status_code=404, detail="Cotizacion no encontrada.")
    return cotizacion


@router.post("", response_model=CotizacionResponse)
async def crear_cotizacion(
    data: CotizacionCreate,
    db: AsyncSession = Depends(get_db),
    usuario_actual: Usuario = Depends(get_current_user),
):
    nueva_cotizacion = Cotizacion(
        id_usuario=usuario_actual.id_usuario,
        nombre_proyecto=data.nombre_proyecto,
    )
    db.add(nueva_cotizacion)
    await db.flush()

    for det in data.detalles:
        db.add(
            DetalleCotizacion(
                id_cotizacion=nueva_cotizacion.id_cotizacion,
                id_producto_maestro=det.id_producto_maestro,
                id_retailer=det.id_retailer,
                cantidad=det.cantidad,
            )
        )

    await db.commit()
    return await _get_user_cotizacion(nueva_cotizacion.id_cotizacion, usuario_actual, db)


@router.get("", response_model=list[CotizacionResponse])
async def listar_mis_cotizaciones(
    db: AsyncSession = Depends(get_db),
    usuario_actual: Usuario = Depends(get_current_user),
):
    query = (
        select(Cotizacion)
        .where(Cotizacion.id_usuario == usuario_actual.id_usuario)
        .options(selectinload(Cotizacion.detalles))
    )
    result = await db.execute(query)
    return result.scalars().all()


@router.get("/{id_cotizacion}", response_model=CotizacionResponse)
async def obtener_cotizacion(
    id_cotizacion: int,
    db: AsyncSession = Depends(get_db),
    usuario_actual: Usuario = Depends(get_current_user),
):
    return await _get_user_cotizacion(id_cotizacion, usuario_actual, db)


@router.put("/{id_cotizacion}", response_model=CotizacionResponse)
async def actualizar_cotizacion(
    id_cotizacion: int,
    data: CotizacionUpdate,
    db: AsyncSession = Depends(get_db),
    usuario_actual: Usuario = Depends(get_current_user),
):
    cotizacion = await _get_user_cotizacion(id_cotizacion, usuario_actual, db)

    if data.nombre_proyecto is not None:
        cotizacion.nombre_proyecto = data.nombre_proyecto
    if data.estado is not None:
        cotizacion.estado = data.estado

    if data.detalles is not None:
        cotizacion.detalles.clear()
        for det in data.detalles:
            cotizacion.detalles.append(
                DetalleCotizacion(
                    id_producto_maestro=det.id_producto_maestro,
                    id_retailer=det.id_retailer,
                    cantidad=det.cantidad,
                )
            )

    await db.commit()
    return await _get_user_cotizacion(id_cotizacion, usuario_actual, db)


@router.delete("/{id_cotizacion}", status_code=status.HTTP_204_NO_CONTENT)
async def eliminar_cotizacion(
    id_cotizacion: int,
    db: AsyncSession = Depends(get_db),
    usuario_actual: Usuario = Depends(get_current_user),
):
    cotizacion = await _get_user_cotizacion(id_cotizacion, usuario_actual, db)
    await db.delete(cotizacion)
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
