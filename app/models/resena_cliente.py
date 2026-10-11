from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class ResenaCliente(Base):
    __tablename__ = "resenas_clientes"
    __table_args__ = (
        CheckConstraint("calificacion >= 1 AND calificacion <= 5", name="ck_resenas_clientes_calificacion"),
        CheckConstraint("estado IN ('pendiente', 'aprobada', 'rechazada')", name="ck_resenas_clientes_estado"),
        UniqueConstraint("usuario_id", name="uq_resenas_clientes_usuario_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    usuario_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id", ondelete="CASCADE"), nullable=False, index=True)
    nombre: Mapped[str | None] = mapped_column(String(100), nullable=True)
    apellido: Mapped[str | None] = mapped_column(String(100), nullable=True)
    calificacion: Mapped[int] = mapped_column(Integer, nullable=False)
    comentario: Mapped[str] = mapped_column(Text, nullable=False)
    estado: Mapped[str] = mapped_column(String(20), nullable=False, default="pendiente", server_default="pendiente", index=True)
    destacada: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false", index=True)
    creada_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), index=True)
    actualizada_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())
