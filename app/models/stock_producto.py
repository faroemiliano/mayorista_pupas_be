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


class StockProducto(Base):
    __tablename__ = "stocks_productos"

    __table_args__ = (
        UniqueConstraint(
            "producto_id",
            "dux_id_deposito",
            "dux_id_det_item",
            name="uq_stock_producto_deposito_detalle",
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

    dux_id_deposito: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        index=True,
    )

    nombre_deposito: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    stock_real: Mapped[float] = mapped_column(
        Numeric(12, 2),
        nullable=False,
        default=0,
        server_default="0",
    )

    stock_reservado: Mapped[float] = mapped_column(
        Numeric(12, 2),
        nullable=False,
        default=0,
        server_default="0",
    )

    stock_disponible: Mapped[float] = mapped_column(
        Numeric(12, 2),
        nullable=False,
        default=0,
        server_default="0",
    )

    dux_id_det_item: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        index=True,
    )

    codigo_barra_detalle: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    talle: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        index=True,
    )

    color: Mapped[str | None] = mapped_column(
        String(80),
        nullable=True,
        index=True,
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
        back_populates="stocks",
    )