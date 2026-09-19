from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.core.security import require_admin, require_cliente
from app.models.usuario import Usuario
from app.repositories.pedido_repository import get_pedido_by_codigo
from app.schemas.pedido_schemas import (
    PedidoCreateRequest,
    PedidoEstado,
    PedidoEstadoRequest,
    PedidoListadoResponse,
    PedidoResponse,
    EnviarDuxRequest,
)
from app.services.dux_pedido_service import DuxPedidoError, enviar_pedido_dux
from app.services.pedido_service import (
    PedidoError,
    actualizar_estado_pedido_service,
    crear_pedido_service,
    get_pedidos_service,
)


router = APIRouter(prefix="/api/pedidos", tags=["Pedidos"])
admin_router = APIRouter(prefix="/api/admin/pedidos", tags=["Administración - Pedidos"], dependencies=[Depends(require_admin)])


@router.post("/", response_model=PedidoResponse, status_code=status.HTTP_201_CREATED)
def crear_pedido(data: PedidoCreateRequest, db: Session = Depends(get_db), usuario: Usuario = Depends(require_cliente)):
    try:
        return crear_pedido_service(db, data, usuario)
    except PedidoError as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from error


@router.get("/mios", response_model=PedidoListadoResponse)
def listar_mis_pedidos(
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=10, ge=1, le=50),
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(require_cliente),
):
    return get_pedidos_service(db, None, page, limit, usuario_id=usuario.id)


@router.get("/{codigo}", response_model=PedidoResponse)
def obtener_pedido(codigo: str, db: Session = Depends(get_db), usuario: Usuario = Depends(require_cliente)):
    pedido = get_pedido_by_codigo(db, codigo)
    if pedido is None or (usuario.rol != "admin" and pedido.usuario_id != usuario.id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pedido no encontrado.")
    return pedido


@admin_router.get("/", response_model=PedidoListadoResponse)
def listar_pedidos_admin(
    estado: PedidoEstado | None = None,
    buscar: str | None = Query(default=None, max_length=150),
    fecha_desde: date | None = None,
    fecha_hasta: date | None = None,
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    try:
        return get_pedidos_service(
            db, estado, page, limit,
            buscar=buscar,
            fecha_desde=fecha_desde,
            fecha_hasta=fecha_hasta,
        )
    except PedidoError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@admin_router.get("/{pedido_id}", response_model=PedidoResponse)
def obtener_pedido_admin(pedido_id: int, db: Session = Depends(get_db)):
    from app.repositories.pedido_repository import get_pedido
    pedido = get_pedido(db, pedido_id)
    if pedido is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pedido no encontrado.")
    return pedido


@admin_router.patch("/{pedido_id}/estado", response_model=PedidoResponse)
def actualizar_estado_pedido(
    pedido_id: int,
    data: PedidoEstadoRequest,
    db: Session = Depends(get_db),
):
    try:
        pedido = actualizar_estado_pedido_service(db, pedido_id, data.estado)
    except PedidoError as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error
    if pedido is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pedido no encontrado.")
    return pedido


@admin_router.post("/{pedido_id}/enviar-dux", response_model=PedidoResponse)
def enviar_a_dux(pedido_id: int, data: EnviarDuxRequest, db: Session = Depends(get_db)):
    try: return enviar_pedido_dux(db, pedido_id, data.id_personal)
    except DuxPedidoError as error: raise HTTPException(status_code=400, detail=str(error)) from error
