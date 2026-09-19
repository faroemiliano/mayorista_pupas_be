from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class Notificacion(Base):
    __tablename__ = "notificaciones"

    id: Mapped[int] = mapped_column(primary_key=True)
    usuario_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id", ondelete="CASCADE"), nullable=True, index=True)
    pedido_id: Mapped[int | None] = mapped_column(ForeignKey("pedidos.id", ondelete="CASCADE"), nullable=True, index=True)
    audiencia: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    tipo: Mapped[str] = mapped_column(String(50), nullable=False)
    titulo: Mapped[str] = mapped_column(String(200), nullable=False)
    mensaje: Mapped[str] = mapped_column(Text, nullable=False)
    enlace_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    leida: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false", index=True)
    email_destino: Mapped[str | None] = mapped_column(String(255), nullable=True)
    email_estado: Mapped[str] = mapped_column(String(20), nullable=False, default="no_configurado", server_default="no_configurado")
    email_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    creada_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), index=True)
