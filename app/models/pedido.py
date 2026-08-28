from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base


if TYPE_CHECKING:
    from app.models.pedido_item import PedidoItem
    from app.models.usuario import Usuario


class Pedido(Base):
    __tablename__ = "pedidos"

    id: Mapped[int] = mapped_column(
        primary_key=True,
        index=True,
    )
    usuario_id: Mapped[int | None] = mapped_column(
        ForeignKey("usuarios.id", ondelete="SET NULL"), nullable=True, index=True
    )
    dux_id_pedido: Mapped[int | None] = mapped_column(nullable=True, unique=True, index=True)
    dux_nro_pedido: Mapped[int | None] = mapped_column(nullable=True)
    dux_id_personal: Mapped[int | None] = mapped_column(nullable=True)
    estado_sync_dux: Mapped[str] = mapped_column(String(30), nullable=False, default="pendiente", server_default="pendiente", index=True)
    error_sync_dux: Mapped[str | None] = mapped_column(Text, nullable=True)
    sincronizado_dux_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    codigo: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        unique=True,
        index=True,
    )
    estado: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="pendiente",
        server_default="pendiente",
        index=True,
    )
    cliente_nombre: Mapped[str] = mapped_column(
        String(150),
        nullable=False,
    )
    cliente_telefono: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )
    cliente_email: Mapped[str | None] = mapped_column(
        String(200),
        nullable=True,
    )
    provincia: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )
    localidad: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )
    direccion: Mapped[str] = mapped_column(
        String(250),
        nullable=False,
    )
    observaciones: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    cantidad_productos_diferentes: Mapped[int] = mapped_column(
        nullable=False,
    )
    cantidad_unidades: Mapped[int] = mapped_column(
        nullable=False,
    )
    aplica_precio_24_productos: Mapped[bool] = mapped_column(
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
    total: Mapped[Decimal] = mapped_column(
        Numeric(14, 2),
        nullable=False,
    )
    creado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        index=True,
    )
    actualizado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    items: Mapped[list["PedidoItem"]] = relationship(
        back_populates="pedido",
        cascade="all, delete-orphan",
        order_by="PedidoItem.id",
    )
    usuario: Mapped["Usuario | None"] = relationship(back_populates="pedidos")
