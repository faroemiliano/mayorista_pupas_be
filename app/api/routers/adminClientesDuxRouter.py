import httpx
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.security import require_admin
from app.database.session import get_db
from app.schemas.admin_cliente_schemas import ClientesDuxListadoResponse, ClientesDuxTotalResponse, EstadoSincronizacionDuxResponse
from app.services.admin_cliente_dux_service import contar_clientes_dux, listar_clientes_dux
from app.services.sincronizacion_cliente_background_service import ejecutar_sincronizacion_background, obtener_estado, preparar_sincronizacion


router = APIRouter(
    prefix="/api/admin/clientes-dux",
    tags=["Administración - Clientes Dux"],
    dependencies=[Depends(require_admin)],
)


@router.get("/total", response_model=ClientesDuxTotalResponse)
def total_clientes(db: Session = Depends(get_db)):
    return contar_clientes_dux(db)


@router.get("/sincronizacion", response_model=EstadoSincronizacionDuxResponse)
def estado_sincronizacion(db: Session = Depends(get_db)):
    return obtener_estado(db)


@router.post("/sincronizar", response_model=EstadoSincronizacionDuxResponse, status_code=status.HTTP_202_ACCEPTED)
def sincronizar(background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    try:
        estado = preparar_sincronizacion(db)
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    background_tasks.add_task(ejecutar_sincronizacion_background)
    return estado


@router.get("/", response_model=ClientesDuxListadoResponse)
def listar(
    pagina: int = Query(default=1, ge=1),
    limite: int = Query(default=20, ge=1, le=50),
    buscar: str | None = Query(default=None, max_length=100),
    db: Session = Depends(get_db),
):
    try:
        return listar_clientes_dux(db, pagina, limite, buscar)
    except httpx.HTTPError as error:
        raise HTTPException(status_code=502, detail="No se pudieron consultar los clientes de Dux.") from error
