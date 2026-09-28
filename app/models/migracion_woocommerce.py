from datetime import datetime

from sqlalchemy import DateTime, JSON, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class MigracionWooCommerce(Base):
    __tablename__ = "migracion_woocommerce"
    __table_args__ = (UniqueConstraint("tipo", "id_externo", name="uq_migracion_woo_tipo_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    tipo: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    id_externo: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    checksum: Mapped[str] = mapped_column(String(64), nullable=False)
    datos: Mapped[dict] = mapped_column(JSON, nullable=False)
    importado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    actualizado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())
