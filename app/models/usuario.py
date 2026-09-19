from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base

if TYPE_CHECKING:
    from app.models.pedido import Pedido


class Usuario(Base):
    __tablename__ = "usuarios"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    google_sub: Mapped[str | None] = mapped_column(String(255), unique=True, nullable=True, index=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    nombre: Mapped[str] = mapped_column(String(200), nullable=False)
    apellido: Mapped[str] = mapped_column(String(200), nullable=False, default="", server_default="")
    telefono: Mapped[str | None] = mapped_column(String(50), nullable=True)
    documento: Mapped[str | None] = mapped_column(String(20), nullable=True, unique=True, index=True)
    provincia: Mapped[str | None] = mapped_column(String(100), nullable=True)
    localidad_partido: Mapped[str | None] = mapped_column(String(150), nullable=True)
    domicilio: Mapped[str | None] = mapped_column(String(250), nullable=True)
    canal_venta: Mapped[str | None] = mapped_column(String(30), nullable=True)
    tienda_online_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    password_hash: Mapped[str | None] = mapped_column(String(500), nullable=True)
    email_verificado: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    acepta_promociones_email: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    estado_registro: Mapped[str] = mapped_column(String(20), nullable=False, default="pendiente", server_default="pendiente", index=True)
    dux_id_cliente: Mapped[int | None] = mapped_column(nullable=True, unique=True, index=True)
    avatar_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    rol: Mapped[str] = mapped_column(String(20), nullable=False, default="cliente", server_default="cliente", index=True)
    activo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    ultimo_acceso_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())

    pedidos: Mapped[list["Pedido"]] = relationship(back_populates="usuario")
