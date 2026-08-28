from pydantic import BaseModel

from app.schemas.categoria_schemas import (
    CategoriaResponse,
)
from app.schemas.marca_schemas import (
    MarcaResponse,
)


class CatalogoFiltrosResponse(BaseModel):
    categorias: list[CategoriaResponse]
    marcas: list[MarcaResponse]
