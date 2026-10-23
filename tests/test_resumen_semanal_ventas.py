from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.notificacion import Notificacion
from app.services.resumen_semanal_ventas_service import crear_resumen_semanal_si_corresponde


def test_crea_un_aviso_semanal_unico_los_viernes(db: Session, monkeypatch):
    monkeypatch.setattr(
        "app.services.resumen_semanal_ventas_service.get_ventas_temporales",
        lambda *_: [
            {"total": Decimal("12000"), "cantidad_unidades": 4},
            {"total": Decimal("8500"), "cantidad_unidades": 2},
        ],
    )
    viernes = datetime(2026, 10, 23, 15, 0, tzinfo=timezone.utc)

    aviso = crear_resumen_semanal_si_corresponde(db, viernes)

    assert aviso is not None
    assert aviso.audiencia == "admin"
    assert aviso.enlace_url == "/admin/analitica?periodo=semana"
    assert "2 pedidos" in aviso.mensaje
    assert "6 unidades" in aviso.mensaje
    assert "$20.500" in aviso.mensaje
    assert crear_resumen_semanal_si_corresponde(db, viernes) is None
    assert db.scalar(select(Notificacion).where(Notificacion.audiencia == "admin")) is not None


def test_no_crea_aviso_fuera_del_viernes(db: Session):
    jueves = datetime(2026, 10, 22, 15, 0, tzinfo=timezone.utc)
    assert crear_resumen_semanal_si_corresponde(db, jueves) is None
