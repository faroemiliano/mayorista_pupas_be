from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base


if TYPE_CHECKING:
    from app.models.pedido import Pedido
    from app.models.producto import Producto


class ReservaStock(Base):
    __tablename__ = "reservas_stock"
    __table_args__ = (
        UniqueConstraint("pedido_id", "producto_id", "talle", name="uq_reserva_pedido_producto_talle"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    pedido_id: Mapped[int] = mapped_column(
        ForeignKey("pedidos.id", ondelete="CASCADE"), nullable=False, index=True
    )
    producto_id: Mapped[int] = mapped_column(
        ForeignKey("productos.id", ondelete="CASCADE"), nullable=False, index=True
    )
    cantidad: Mapped[int] = mapped_column(Integer, nullable=False)
    talle: Mapped[int | None] = mapped_column(Integer, nullable=True)
    estado: Mapped[str] = mapped_column(
        String(30), nullable=False, default="activa", server_default="activa", index=True
    )
    reservada_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    liberada_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reconciliada_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    pedido: Mapped["Pedido"] = relationship(back_populates="reservas_stock")
    producto: Mapped["Producto"] = relationship()
