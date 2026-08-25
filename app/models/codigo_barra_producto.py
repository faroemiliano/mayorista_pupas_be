from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    DateTime,
    ForeignKey,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base


if TYPE_CHECKING:
    from app.models.producto import Producto


class CodigoBarraProducto(Base):
    __tablename__ = "codigos_barra_productos"

    __table_args__ = (
        UniqueConstraint(
            "producto_id",
            "codigo",
            name="uq_producto_codigo_barra",
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

    codigo: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
    )

    creado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    producto: Mapped["Producto"] = relationship(
        back_populates="codigos_barra",
    )