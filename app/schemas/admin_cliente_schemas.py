from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ClienteDuxResponse(BaseModel):
    id_cliente: int
    codigo: str | None = None
    nombre: str
    email: str | None = None
    telefono: str | None = None
    tipo_doc: str | None = None
    nro_doc: str | None = None
    cuit_cuil: str | None = None
    localidad: str | None = None
    provincia: str | None = None
    habilitado: bool = True
    fecha_creacion: datetime | None = None
    usuario_id: int | None = None
    usuario_estado: str | None = None
    criterio_vinculacion: str | None = None


class ClientesDuxListadoResponse(BaseModel):
    items: list[ClienteDuxResponse]
    total: int
    pagina: int
    limite: int
    hay_mas: bool
    ultima_sincronizacion: datetime | None = None


class ClientesDuxTotalResponse(BaseModel):
    total: int
    cache_segundos: int


class SincronizacionClientesDuxResponse(BaseModel):
    procesados: int
    creados: int
    actualizados: int
    total_local: int
    sincronizado_en: datetime


class EstadoSincronizacionDuxResponse(BaseModel):
    estado: str
    procesados: int
    creados: int
    actualizados: int
    total_local: int
    error: str | None = None
    iniciada_en: datetime | None = None
    finalizada_en: datetime | None = None

    model_config = ConfigDict(from_attributes=True)
