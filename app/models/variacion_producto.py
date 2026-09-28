from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, JSON, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base

if TYPE_CHECKING:
    from app.models.producto import Producto


class VariacionProducto(Base):
    __tablename__ = "variaciones_productos"

    id: Mapped[int] = mapped_column(primary_key=True)
    producto_id: Mapped[int] = mapped_column(ForeignKey("productos.id", ondelete="CASCADE"), nullable=False, index=True)
    wordpress_id: Mapped[int] = mapped_column(Integer, nullable=False, unique=True, index=True)
    sku: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    atributos: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    precio: Mapped[float | None] = mapped_column(Numeric(12, 2), nullable=True)
    stock: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    estado_stock: Mapped[str | None] = mapped_column(String(30), nullable=True)
    habilitada: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    actualizado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())

    producto: Mapped["Producto"] = relationship(back_populates="variaciones")
