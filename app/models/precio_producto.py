from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base


if TYPE_CHECKING:
    from app.models.producto import Producto


class PrecioProducto(Base):
    __tablename__ = "precios_productos"

    __table_args__ = (
        UniqueConstraint(
            "producto_id",
            "dux_id_lista",
            name="uq_precio_producto_lista",
        ),
    )

    id: Mapped[int] = mapped_column(
        primary_key=True,
        index=True,
    )

    producto_id: Mapped[int] = mapped_column(
        ForeignKey(
            "productos.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    dux_id_lista: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        index=True,
    )

    nombre_lista: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
    )

    precio: Mapped[float] = mapped_column(
        Numeric(12, 2),
        nullable=False,
        default=0,
        server_default="0",
    )

    creado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    actualizado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    producto: Mapped["Producto"] = relationship(
        back_populates="precios",
    )