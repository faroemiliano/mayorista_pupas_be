from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.core.config import settings
from app.core.security import require_admin


router = APIRouter(
    prefix="/api/admin/configuracion",
    tags=["Administración - Configuración"],
    dependencies=[Depends(require_admin)],
)


class EstadoDuxResponse(BaseModel):
    escritura_habilitada: bool
    modo: str


@router.get("/dux", response_model=EstadoDuxResponse)
def estado_dux():
    habilitada = settings.DUX_ESCRITURA_HABILITADA
    return {
        "escritura_habilitada": habilitada,
        "modo": "produccion" if habilitada else "desarrollo",
    }
