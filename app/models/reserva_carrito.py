from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base

if TYPE_CHECKING:
    from app.models.producto import Producto
    from app.models.usuario import Usuario


class ReservaCarrito(Base):
    __tablename__ = "reservas_carrito"
    __table_args__ = (UniqueConstraint("usuario_id", "producto_id", "talle", name="uq_reserva_carrito_usuario_producto_talle"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    usuario_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id", ondelete="CASCADE"), nullable=False, index=True)
    producto_id: Mapped[int] = mapped_column(ForeignKey("productos.id", ondelete="CASCADE"), nullable=False, index=True)
    talle: Mapped[str] = mapped_column(String(30), nullable=False)
    cantidad: Mapped[int] = mapped_column(Integer, nullable=False)
    reservada_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    expira_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)

    usuario: Mapped["Usuario"] = relationship()
    producto: Mapped["Producto"] = relationship()
