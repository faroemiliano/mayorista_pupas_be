from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base

if TYPE_CHECKING:
    from app.models.usuario import Usuario


class UsuarioWordpress(Base):
    __tablename__ = "usuarios_wordpress"

    id: Mapped[int] = mapped_column(primary_key=True)
    wordpress_id: Mapped[int] = mapped_column(Integer, nullable=False, unique=True, index=True)
    usuario_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id", ondelete="CASCADE"), nullable=False, index=True)
    email_original: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())

    usuario: Mapped["Usuario"] = relationship()
