from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class SincronizacionDux(Base):
    __tablename__ = "sincronizaciones_dux"

    id: Mapped[int] = mapped_column(primary_key=True)
    recurso: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    estado: Mapped[str] = mapped_column(String(20), nullable=False, default="pendiente")
    procesados: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    creados: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    actualizados: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_local: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    iniciada_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finalizada_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    actualizado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())
