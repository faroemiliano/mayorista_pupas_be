from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from typing import TYPE_CHECKING

from app.database.base import Base

if TYPE_CHECKING:
    from app.models.producto import Producto


class PortadaInicio(Base):
    __tablename__ = "portadas_inicio"

    id: Mapped[int] = mapped_column(primary_key=True)
    slide_id: Mapped[str] = mapped_column(String(40), unique=True, nullable=False, index=True)
    imagen_url: Mapped[str] = mapped_column(String(700), nullable=False)
    media_type: Mapped[str] = mapped_column(String(50), nullable=False)
    producto_id: Mapped[int | None] = mapped_column(
        ForeignKey("productos.id", ondelete="SET NULL"), nullable=True, index=True
    )
    actualizada_por_id: Mapped[int | None] = mapped_column(
        ForeignKey("usuarios.id", ondelete="SET NULL"), nullable=True
    )
    actualizada_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
    producto: Mapped["Producto | None"] = relationship()
