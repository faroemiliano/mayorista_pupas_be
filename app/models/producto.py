from datetime import date, datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base


if TYPE_CHECKING:
    from app.models.categoria import Categoria
    from app.models.codigo_barra_producto import CodigoBarraProducto
    from app.models.imagen_producto import ImagenProducto
    from app.models.marca import Marca
    from app.models.precio_producto import PrecioProducto
    from app.models.stock_producto import StockProducto
    from app.models.subcategoria import Subcategoria


class Producto(Base):
    __tablename__ = "productos"

    id: Mapped[int] = mapped_column(
        primary_key=True,
        index=True,
    )

    dux_codigo: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        unique=True,
        index=True,
    )

    nombre: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
        index=True,
    )

    slug: Mapped[str] = mapped_column(
        String(220),
        nullable=False,
        unique=True,
        index=True,
    )

    codigo_externo: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    descripcion: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    costo: Mapped[float | None] = mapped_column(
        Numeric(12, 2),
        nullable=True,
    )

    porcentaje_iva: Mapped[float | None] = mapped_column(
        Numeric(5, 2),
        nullable=True,
    )

    imagen_url: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
    )

    cantidad_unidades_por_bulto: Mapped[float | None] = mapped_column(
        Numeric(12, 2),
        nullable=True,
    )

    habilitado: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default="true",
    )

    fecha_creacion_dux: Mapped[date | None] = mapped_column(
        Date,
        nullable=True,
    )

    categoria_id: Mapped[int | None] = mapped_column(
        ForeignKey(
            "categorias.id",
            ondelete="SET NULL",
        ),
        nullable=True,
        index=True,
    )

    subcategoria_id: Mapped[int | None] = mapped_column(
        ForeignKey(
            "subcategorias.id",
            ondelete="SET NULL",
        ),
        nullable=True,
        index=True,
    )

    marca_id: Mapped[int | None] = mapped_column(
        ForeignKey(
            "marcas.id",
            ondelete="SET NULL",
        ),
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

    categoria: Mapped["Categoria | None"] = relationship(
        back_populates="productos",
    )

    subcategoria: Mapped["Subcategoria | None"] = relationship(
        back_populates="productos",
    )

    marca: Mapped["Marca | None"] = relationship(
        back_populates="productos",
    )

    precios: Mapped[list["PrecioProducto"]] = relationship(
        back_populates="producto",
        cascade="all, delete-orphan",
    )

    stocks: Mapped[list["StockProducto"]] = relationship(
        back_populates="producto",
        cascade="all, delete-orphan",
    )

    imagenes: Mapped[list["ImagenProducto"]] = relationship(
        back_populates="producto",
        cascade="all, delete-orphan",
        order_by="ImagenProducto.orden",
    )

    codigos_barra: Mapped[
        list["CodigoBarraProducto"]
    ] = relationship(
        back_populates="producto",
        cascade="all, delete-orphan",
    )