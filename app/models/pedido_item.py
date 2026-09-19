from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base


if TYPE_CHECKING:
    from app.models.pedido import Pedido
    from app.models.producto import Producto


class PedidoItem(Base):
    __tablename__ = "pedidos_items"

    id: Mapped[int] = mapped_column(
        primary_key=True,
        index=True,
    )
    pedido_id: Mapped[int] = mapped_column(
        ForeignKey("pedidos.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    producto_id: Mapped[int | None] = mapped_column(
        ForeignKey("productos.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    dux_codigo: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )
    producto_nombre: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
    )
    cantidad: Mapped[int] = mapped_column(
        nullable=False,
    )
    talle: Mapped[int | None] = mapped_column(Integer, nullable=True)
    precio_mayorista: Mapped[Decimal] = mapped_column(
        Numeric(14, 2),
        nullable=False,
    )
    precio_unitario: Mapped[Decimal] = mapped_column(
        Numeric(14, 2),
        nullable=False,
    )
    subtotal_sin_descuento: Mapped[Decimal] = mapped_column(
        Numeric(14, 2),
        nullable=False,
    )
    descuento_aplicado: Mapped[Decimal] = mapped_column(
        Numeric(14, 2),
        nullable=False,
    )
    subtotal: Mapped[Decimal] = mapped_column(
        Numeric(14, 2),
        nullable=False,
    )

    pedido: Mapped["Pedido"] = relationship(
        back_populates="items",
    )
    producto: Mapped["Producto | None"] = relationship()
