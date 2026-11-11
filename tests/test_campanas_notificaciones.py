from sqlalchemy import select
from sqlalchemy.orm import Session
from fastapi.testclient import TestClient

from app.models.notificacion import Notificacion
from app.models.usuario import Usuario
from app.services.notificacion_service import crear_campana
from app.core.security import hashear_password


def _cliente(
    db: Session,
    numero: int,
    acepta_email: bool,
    *,
    password_hash: str | None = "hash-activo",
    google_sub: str | None = None,
    requiere_migracion_password: bool = False,
) -> Usuario:
    usuario = Usuario(
        email=f"cliente{numero}@example.com",
        nombre=f"Cliente {numero}",
        apellido="",
        password_hash=password_hash,
        google_sub=google_sub,
        rol="cliente",
        activo=True,
        estado_registro="aprobado",
        acepta_promociones_email=acepta_email,
        requiere_migracion_password=requiere_migracion_password,
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


def test_campana_se_mantiene_dentro_de_la_plataforma(db: Session):
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
    )

    assert creadas == 2
    assert emails == 0
    items = {
        item.usuario_id: item
        for item in db.scalars(select(Notificacion)).all()
    }
    assert items[acepta.id].email_estado == "omitido"
    assert items[acepta.id].email_destino is None
    assert items[rechaza.id].email_estado == "omitido"
    assert items[rechaza.id].email_destino is None


def test_campana_excluye_clientes_migrados_que_no_activaron_su_cuenta(db: Session):
    activo = _cliente(db, 1, True)
    google = _cliente(db, 2, True, password_hash=None, google_sub="google-2")
    _cliente(
        db,
        3,
        True,
        password_hash=None,
        requiere_migracion_password=True,
    )
    db.commit()

    creadas, emails, _ = crear_campana(
        db,
        tipo="informacion",
        titulo="Información importante",
        mensaje="Este mensaje es para quienes ya usan el sitio nuevo.",
        destinatarios="todos",
        usuario_ids=[],
    )

    assert creadas == 2
    assert emails == 0
    destinatarios = set(db.scalars(select(Notificacion.usuario_id)).all())
    assert destinatarios == {activo.id, google.id}


def test_campana_seleccionada_no_incluye_cuenta_sin_activar(db: Session):
    pendiente = _cliente(
        db,
        1,
        True,
        password_hash=None,
        requiere_migracion_password=True,
    )
    db.commit()

    try:
        crear_campana(
            db,
            tipo="oferta",
            titulo="Oferta",
            mensaje="Promoción para clientes activos.",
            destinatarios="seleccionados",
            usuario_ids=[pendiente.id],
        )
    except ValueError as error:
        assert str(error) == "No hay clientes activos y habilitados para esta campaña."
    else:
        raise AssertionError("La campaña no debe incluir una cuenta migrada sin activar.")


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
