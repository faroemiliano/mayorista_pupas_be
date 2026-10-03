from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    status,
)
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.core.security import require_cliente
from app.models.usuario import Usuario
from app.schemas.carrito_schemas import (
    CarritoCalcularRequest,
    CarritoCalcularResponse,
    CarritoReservaRequest,
    CarritoReservaResponse,
)
from app.services.carrito_service import (
    CarritoError,
    calcular_carrito_service,
    reservar_carrito_service,
)


router = APIRouter(
    prefix="/api/carrito",
    tags=["Carrito"],
)


@router.put("/reserva", response_model=CarritoReservaResponse)
def reservar_carrito(carrito: CarritoReservaRequest, db: Session = Depends(get_db), usuario: Usuario = Depends(require_cliente)):
    try:
        return reservar_carrito_service(db, carrito, usuario.id)
    except CarritoError as error:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error


# =========================================================
# CALCULAR CARRITO
# =========================================================

@router.post(
    "/calcular",
    response_model=CarritoCalcularResponse,
)
def calcular_carrito(
    carrito: CarritoCalcularRequest,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(require_cliente),
):

    try:
        return calcular_carrito_service(
            db=db,
            carrito=carrito,
            usuario_id=usuario.id,
        )

    except CarritoError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error),
        ) from error
