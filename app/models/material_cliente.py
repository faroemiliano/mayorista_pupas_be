from datetime import datetime

from sqlalchemy import DateTime, LargeBinary, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class MaterialCliente(Base):
    __tablename__ = "materiales_clientes"

    id: Mapped[int] = mapped_column(primary_key=True)
    titulo: Mapped[str] = mapped_column(String(160), nullable=False)
    descripcion: Mapped[str | None] = mapped_column(Text, nullable=True)
    nombre_archivo: Mapped[str] = mapped_column(String(255), nullable=False)
    tipo_contenido: Mapped[str] = mapped_column(String(50), nullable=False)
    contenido: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    creado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), index=True
    )
