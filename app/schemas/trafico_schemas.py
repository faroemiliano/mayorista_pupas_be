from pydantic import BaseModel


class TraficoResumenResponse(BaseModel):
    usuarios: int
    sesiones: int
    vistas_paginas: int
    usuarios_activos_ahora: int | None = None


class TraficoDiarioResponse(BaseModel):
    fecha: str
    etiqueta: str
    usuarios: int
    sesiones: int
    vistas_paginas: int


class TraficoPaginaResponse(BaseModel):
    ruta: str
    vistas_paginas: int
    usuarios: int


class TraficoDispositivoResponse(BaseModel):
    dispositivo: str
    usuarios: int


class TraficoAnalyticsResponse(BaseModel):
    dias: int
    fecha: str | None = None
    resumen: TraficoResumenResponse
    serie_diaria: list[TraficoDiarioResponse]
    paginas_populares: list[TraficoPaginaResponse]
    dispositivos: list[TraficoDispositivoResponse]
    actualizado_en: str
    fuente: str = "Google Analytics 4"
