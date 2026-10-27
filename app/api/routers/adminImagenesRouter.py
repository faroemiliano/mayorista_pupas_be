from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.security import require_admin_total
from app.database.session import get_db
from app.services.diagnostico_imagenes_r2_service import obtener_diagnostico_avanzado_imagenes_r2


router = APIRouter(
    prefix="/api/admin/imagenes",
    tags=["Administración - Imágenes"],
    dependencies=[Depends(require_admin_total)],
)


@router.get("/diagnostico-r2")
def diagnostico_r2(db: Session = Depends(get_db)):
    """Audita referencias y tamaños sin modificar catálogo ni almacenamiento."""
    try:
        return obtener_diagnostico_avanzado_imagenes_r2(db)
    except Exception as error:
        raise HTTPException(502, "No se pudo completar el diagnóstico de imágenes.") from error
