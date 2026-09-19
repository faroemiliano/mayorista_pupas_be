from typing import TYPE_CHECKING
from sqlalchemy import CheckConstraint, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database.base import Base

if TYPE_CHECKING:
    from app.models.producto import Producto

class StockTalleProducto(Base):
    __tablename__ = "stocks_talles_productos"
    __table_args__ = (
        UniqueConstraint("producto_id", "talle", name="uq_stock_talle_producto"),
        CheckConstraint("talle BETWEEN 1 AND 5", name="ck_stock_talle_1_5"),
        CheckConstraint("cantidad >= 0", name="ck_stock_talle_no_negativo"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    producto_id: Mapped[int] = mapped_column(ForeignKey("productos.id", ondelete="CASCADE"), index=True)
    talle: Mapped[int] = mapped_column(Integer, nullable=False)
    cantidad: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    origen: Mapped[str] = mapped_column(String(20), nullable=False, default="manual", server_default="manual")
    producto: Mapped["Producto"] = relationship(back_populates="stocks_talles")
