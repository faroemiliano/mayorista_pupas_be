from datetime import datetime

from pydantic import BaseModel, Field


class MaterialClienteCreate(BaseModel):
    titulo: str = Field(min_length=2, max_length=160)
    descripcion: str | None = Field(default=None, max_length=1000)
    nombre_archivo: str = Field(min_length=1, max_length=255)
    contenido_base64: str = Field(min_length=4, max_length=12_000_000)


class ArchivoMaterialCreate(BaseModel):
    nombre_archivo: str = Field(min_length=1, max_length=255)
    contenido_base64: str = Field(min_length=4, max_length=12_000_000)


class MaterialClienteBatchCreate(BaseModel):
    titulo: str = Field(min_length=2, max_length=160)
    descripcion: str | None = Field(default=None, max_length=1000)
    archivos: list[ArchivoMaterialCreate] = Field(min_length=1, max_length=20)


class MaterialClienteResponse(BaseModel):
    id: int
    titulo: str
    descripcion: str | None
    nombre_archivo: str
    tipo_contenido: str
    creado_en: datetime
