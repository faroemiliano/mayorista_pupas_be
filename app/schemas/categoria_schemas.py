from pydantic import BaseModel, ConfigDict, Field


# =========================================================
# SUBCATEGORÍA
# =========================================================

class SubcategoriaResponse(BaseModel):
    id: int
    dux_id: int | None
    categoria_id: int
    nombre: str
    slug: str
    descripcion: str | None
    activo: bool

    model_config = ConfigDict(
        from_attributes=True,
    )


# =========================================================
# CATEGORÍA
# =========================================================

class CategoriaSimpleResponse(BaseModel):
    id: int
    dux_id: int | None
    nombre: str
    slug: str
    descripcion: str | None
    activo: bool

    model_config = ConfigDict(
        from_attributes=True,
    )


class CategoriaResponse(
    CategoriaSimpleResponse
):
    subcategorias: list[
        SubcategoriaResponse
    ] = Field(
        default_factory=list
    )


# =========================================================
# SUBCATEGORÍA CON CATEGORÍA
# =========================================================

class SubcategoriaDetalleResponse(
    SubcategoriaResponse
):
    categoria: CategoriaSimpleResponse
