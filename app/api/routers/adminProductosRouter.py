from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.core.security import require_admin
from app.schemas.admin_producto_schemas import ProductoAnaliticaResponse
from app.services.admin_producto_service import get_analitica_productos_service


router = APIRouter(prefix="/api/admin/productos", tags=["Administración - Productos"], dependencies=[Depends(require_admin)])


@router.get("/analitica", response_model=ProductoAnaliticaResponse)
def obtener_analitica_productos(
    dias: int = Query(default=30, ge=0, le=3650),
    limit: int = Query(default=10, ge=1, le=50),
    db: Session = Depends(get_db),
):
    return get_analitica_productos_service(db, None if dias == 0 else dias, limit)
