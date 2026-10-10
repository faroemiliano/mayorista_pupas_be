from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query

from app.core.security import require_admin_total
from app.schemas.trafico_schemas import TraficoAnalyticsResponse
from app.services.ga4_analytics_service import GA4AnalyticsError, obtener_trafico_ga4


router = APIRouter(
    prefix="/api/admin/trafico",
    tags=["Administración - Tráfico"],
)


@router.get("", response_model=TraficoAnalyticsResponse)
def obtener_trafico(
    dias: int = Query(default=7, ge=7, le=30),
    fecha: date | None = Query(default=None),
    _: object = Depends(require_admin_total),
):
    if dias not in {7, 30}:
        raise HTTPException(status_code=422, detail="Elegí un período de 7 o 30 días.")
    try:
        return obtener_trafico_ga4(dias, fecha)
    except GA4AnalyticsError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
