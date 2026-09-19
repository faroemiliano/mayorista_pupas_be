from sqlalchemy import select
from sqlalchemy.orm import Session
from fastapi.testclient import TestClient

from app.models.notificacion import Notificacion
from app.models.usuario import Usuario
from app.services.notificacion_service import crear_campana
from app.core.security import hashear_password


def _cliente(db: Session, numero: int, acepta_email: bool) -> Usuario:
    usuario = Usuario(
        email=f"cliente{numero}@example.com",
        nombre=f"Cliente {numero}",
        apellido="",
        rol="cliente",
        activo=True,
        estado_registro="aprobado",
        acepta_promociones_email=acepta_email,
    )
    db.add(usuario)
    db.flush()
    return usuario


def test_admin_crea_campana_interna_para_clientes_aprobados(
    client: TestClient,
    db: Session,
):
    _cliente(db, 1, True)
    _cliente(db, 2, False)
    db.commit()

    response = client.post(
        "/api/notificaciones/admin/campanas",
        json={
            "tipo": "nuevo_producto",
            "titulo": "Nueva colección",
            "mensaje": "Ya podés conocer los nuevos modelos.",
            "destinatarios": "todos",
            "usuario_ids": [],
            "enviar_email": False,
        },
    )

    assert response.status_code == 201, response.text
    assert response.json() == {
        "notificaciones_creadas": 2,
        "emails_programados": 0,
    }
    items = list(db.scalars(select(Notificacion).where(Notificacion.audiencia == "cliente")).all())
    assert len(items) == 2
    assert all(item.enlace_url is None for item in items)


def test_email_promocional_solo_se_programa_con_consentimiento(db: Session):
    acepta = _cliente(db, 1, True)
    rechaza = _cliente(db, 2, False)
    db.commit()

    creadas, emails, _ = crear_campana(
        db,
        tipo="oferta",
        titulo="Oferta mayorista",
        mensaje="Descuento especial por esta semana.",
        destinatarios="todos",
        usuario_ids=[],
        enviar_email=True,
    )

    assert creadas == 2
    assert emails == 1
    items = {
        item.usuario_id: item
        for item in db.scalars(select(Notificacion)).all()
    }
    assert items[acepta.id].email_estado == "pendiente"
    assert items[acepta.id].email_destino == acepta.email
    assert items[rechaza.id].email_estado == "omitido"
    assert items[rechaza.id].email_destino is None


def test_primer_login_crea_una_sola_notificacion_de_bienvenida(
    public_client: TestClient,
    db: Session,
):
    usuario = Usuario(
        email="bienvenida@example.com",
        nombre="María",
        apellido="",
        password_hash=hashear_password("clave-segura"),
        rol="cliente",
        activo=True,
        estado_registro="aprobado",
    )
    db.add(usuario)
    db.commit()

    credenciales = {
        "email": "bienvenida@example.com",
        "password": "clave-segura",
    }
    primera = public_client.post("/api/auth/login", json=credenciales)
    segunda = public_client.post("/api/auth/login", json=credenciales)

    assert primera.status_code == 200, primera.text
    assert segunda.status_code == 200, segunda.text
    bienvenidas = list(
        db.scalars(
            select(Notificacion).where(
                Notificacion.usuario_id == usuario.id,
                Notificacion.tipo == "bienvenida",
            )
        ).all()
    )
    assert len(bienvenidas) == 1
    assert bienvenidas[0].leida is False
    assert "ofertas" in bienvenidas[0].mensaje
    assert "pedidos" in bienvenidas[0].mensaje
