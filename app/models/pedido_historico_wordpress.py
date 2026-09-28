from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Integer, JSON, Numeric, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base

if TYPE_CHECKING:
    from app.models.usuario import Usuario


class PedidoHistoricoWordpress(Base):
    __tablename__ = "pedidos_historicos_wordpress"

    id: Mapped[int] = mapped_column(primary_key=True)
    wordpress_id: Mapped[int] = mapped_column(Integer, nullable=False, unique=True, index=True)
    numero: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    usuario_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id", ondelete="SET NULL"), nullable=True, index=True)
    wordpress_customer_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    estado: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    moneda: Mapped[str] = mapped_column(String(10), nullable=False, default="ARS", server_default="ARS")
    total: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False, default=0, server_default="0")
    descuento_total: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False, default=0, server_default="0")
    envio_total: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False, default=0, server_default="0")
    impuesto_total: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False, default=0, server_default="0")
    metodo_pago: Mapped[str | None] = mapped_column(String(100), nullable=True)
    titulo_pago: Mapped[str | None] = mapped_column(String(200), nullable=True)
    facturacion: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    envio: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    creado_en_wordpress: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    pagado_en_wordpress: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completado_en_wordpress: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    importado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())

    usuario: Mapped["Usuario | None"] = relationship()
    items: Mapped[list["PedidoItemHistoricoWordpress"]] = relationship(
        back_populates="pedido", cascade="all, delete-orphan", order_by="PedidoItemHistoricoWordpress.id"
    )


class PedidoItemHistoricoWordpress(Base):
    __tablename__ = "pedidos_items_historicos_wordpress"
    __table_args__ = (UniqueConstraint("pedido_id", "wordpress_id", name="uq_pedido_historico_item_wordpress"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    pedido_id: Mapped[int] = mapped_column(ForeignKey("pedidos_historicos_wordpress.id", ondelete="CASCADE"), nullable=False, index=True)
    wordpress_id: Mapped[int] = mapped_column(Integer, nullable=False)
    wordpress_product_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    wordpress_variation_id: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0", index=True)
    producto_id: Mapped[int | None] = mapped_column(ForeignKey("productos.id", ondelete="SET NULL"), nullable=True, index=True)
    nombre: Mapped[str] = mapped_column(String(250), nullable=False)
    sku: Mapped[str | None] = mapped_column(String(100), nullable=True)
    cantidad: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    subtotal: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False, default=0, server_default="0")
    total: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False, default=0, server_default="0")
    impuesto_total: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False, default=0, server_default="0")
    precio_unitario: Mapped[float | None] = mapped_column(Numeric(14, 2), nullable=True)
    metadatos: Mapped[list] = mapped_column(JSON, nullable=False, default=list)

    pedido: Mapped["PedidoHistoricoWordpress"] = relationship(back_populates="items")
