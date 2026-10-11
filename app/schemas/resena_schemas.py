from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class ResenaCrearRequest(BaseModel):
    calificacion: int = Field(ge=1, le=5)
    comentario: str = Field(min_length=10, max_length=800)
    nombre: str | None = Field(default=None, max_length=100)
    apellido: str | None = Field(default=None, max_length=100)


class ResenaModeracionRequest(BaseModel):
    estado: Literal["pendiente", "aprobada", "rechazada"] | None = None
    destacada: bool | None = None


class ResenaResponse(BaseModel):
    id: int
    calificacion: int
    comentario: str
    estado: Literal["pendiente", "aprobada", "rechazada"]
    destacada: bool
    creada_en: datetime
    nombre: str | None = None
    apellido: str | None = None
    cliente_nombre: str | None = None
    cliente_email: str | None = None
