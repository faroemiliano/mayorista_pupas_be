from datetime import datetime

from sqlalchemy import Boolean, DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class ClienteDux(Base):
    __tablename__ = "clientes_dux"

    id: Mapped[int] = mapped_column(primary_key=True)
    dux_id_cliente: Mapped[int] = mapped_column(unique=True, index=True)
    codigo: Mapped[str | None] = mapped_column(String(100), nullable=True)
    nombre: Mapped[str] = mapped_column(String(250), index=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    telefono: Mapped[str | None] = mapped_column(String(100), nullable=True)
    tipo_doc: Mapped[str | None] = mapped_column(String(30), nullable=True)
    nro_doc: Mapped[str | None] = mapped_column(String(30), nullable=True, index=True)
    cuit_cuil: Mapped[str | None] = mapped_column(String(30), nullable=True, index=True)
    domicilio: Mapped[str | None] = mapped_column(String(300), nullable=True)
    localidad: Mapped[str | None] = mapped_column(String(150), nullable=True)
    provincia: Mapped[str | None] = mapped_column(String(150), nullable=True)
    habilitado: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    presente_en_dux: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true", index=True)
    fecha_creacion_dux: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    sincronizado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    actualizado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())
