from pydantic import BaseModel, ConfigDict


class MarcaResponse(BaseModel):
    id: int
    dux_id: int | None
    nombre: str
    slug: str
    activo: bool

    model_config = ConfigDict(
        from_attributes=True,
    )
