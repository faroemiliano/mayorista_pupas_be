from fastapi import APIRouter
from pydantic import BaseModel
from app.core.config import settings

router=APIRouter(prefix="/api/configuracion",tags=["Configuración pública"])

class ConfiguracionPublicaResponse(BaseModel):
    whatsapp_empresa:str|None

@router.get("/publica",response_model=ConfiguracionPublicaResponse)
def publica():return {"whatsapp_empresa":settings.WHATSAPP_EMPRESA or None}
