from datetime import datetime
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field


class NotificacionResponse(BaseModel):
    id: int
    pedido_id: int | None
    tipo: str
    titulo: str
    mensaje: str
    enlace_url: str | None
    leida: bool
    creada_en: datetime
    model_config = ConfigDict(from_attributes=True)


class NotificacionesResponse(BaseModel):
    items: list[NotificacionResponse]
    no_leidas: int


class CampanaNotificacionRequest(BaseModel):
    tipo: Literal["nuevo_producto", "oferta", "reposicion", "informacion"]
    titulo: str = Field(min_length=3, max_length=200)
    mensaje: str = Field(min_length=5, max_length=2000)
    destinatarios: Literal["todos", "seleccionados"] = "todos"
    usuario_ids: list[int] = Field(default_factory=list, max_length=500)
    enviar_email: bool = False


class CampanaNotificacionResponse(BaseModel):
    notificaciones_creadas: int
    emails_programados: int
