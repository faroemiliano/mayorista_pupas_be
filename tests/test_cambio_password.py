from datetime import datetime, timedelta, timezone
import hashlib

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.security import crear_token, hashear_password
from app.database.session import get_db
from app.main import app
from app.models.usuario import Usuario
from app.api.routers.authRouter import _fecha_en_utc
from app.services.password_reset_email_service import construir_email_restablecimiento


def test_email_restablecimiento_incluye_identidad_visual_de_pupas():
    texto, html = construir_email_restablecimiento(
        nombre="Ana & Asociados",
        enlace="https://mayorista.pupas.com/restablecer-clave?token=abc&tipo=cliente",
        logo_url="https://mayorista.pupas.com/brand/logo-pupas.jpg",
    )

    assert "Hola, Ana & Asociados." in texto
    assert "Crear mi nueva contraseña" in texto
    assert "logo-pupas.jpg" in html
    assert "Pupas Mayorista" in html
    assert "Ana &amp; Asociados" in html
    assert "token=abc&amp;tipo=cliente" in html


def test_solicitud_reset_envia_email_html_con_logo(engine, monkeypatch):
    with Session(engine) as db:
        db.add(Usuario(
            email="migrada@test.local",
            nombre="Cliente Pupas",
            password_hash=None,
            rol="cliente",
            activo=True,
            estado_registro="aprobado",
            origen="wordpress",
            wordpress_id=456,
            requiere_migracion_password=True,
        ))
        db.commit()

    enviados = []

    class RespuestaExitosa:
        def raise_for_status(self):
            return None

    def enviar(*args, **kwargs):
        enviados.append((args, kwargs))
        return RespuestaExitosa()

    monkeypatch.setattr("app.api.routers.authRouter.settings.RESEND_API_KEY", "resend-test")
    monkeypatch.setattr("app.api.routers.authRouter.settings.EMAIL_FROM", "Pupas <hola@test.local>")
    monkeypatch.setattr("app.api.routers.authRouter.settings.FRONTEND_URL", "https://mayorista.pupas.test")
    monkeypatch.setattr("app.api.routers.authRouter.httpx.post", enviar)

    def override_get_db():
        with Session(engine) as db:
            yield db

    app.dependency_overrides[get_db] = override_get_db
    try:
        with TestClient(app) as client:
            response = client.post(
                "/api/auth/solicitar-reset-password",
                json={"email": "migrada@test.local"},
            )
        assert response.status_code == 200
        payload = enviados[0][1]["json"]
        assert payload["to"] == ["migrada@test.local"]
        assert "logo-pupas.jpg" in payload["html"]
        assert "Cliente Pupas" in payload["html"]
        assert "restablecer-clave?token=" in payload["text"]
    finally:
        app.dependency_overrides.clear()


def test_usuario_cambia_su_password(engine):
    with Session(engine) as db:
        usuario = Usuario(
            email="cliente@test.local",
            nombre="Cliente Test",
            password_hash=hashear_password("password-anterior"),
            rol="cliente",
            activo=True,
            estado_registro="aprobado",
        )
        db.add(usuario)
        db.commit()
        db.refresh(usuario)
        token = crear_token(usuario)

    def override_get_db():
        with Session(engine) as db:
            yield db

    app.dependency_overrides[get_db] = override_get_db
    try:
        with TestClient(app) as client:
            headers = {"Authorization": f"Bearer {token}"}
            incorrecta = client.patch(
                "/api/auth/me/password",
                headers=headers,
                json={
                    "password_actual": "password-equivocada",
                    "password_nueva": "password-nueva",
                    "confirmar_password": "password-nueva",
                },
            )
            assert incorrecta.status_code == 400

            correcta = client.patch(
                "/api/auth/me/password",
                headers=headers,
                json={
                    "password_actual": "password-anterior",
                    "password_nueva": "password-nueva",
                    "confirmar_password": "password-nueva",
                },
            )
            assert correcta.status_code == 200

            login_anterior = client.post(
                "/api/auth/login",
                json={"email": "cliente@test.local", "password": "password-anterior"},
            )
            assert login_anterior.status_code == 401

            login_nuevo = client.post(
                "/api/auth/login",
                json={"email": "cliente@test.local", "password": "password-nueva"},
            )
            assert login_nuevo.status_code == 200
    finally:
        app.dependency_overrides.clear()


def test_cuenta_migrada_crea_password_desde_email_y_puede_ingresar(engine):
    token_reset = "token-seguro-de-prueba-con-longitud-valida-123456"
    with Session(engine) as db:
        usuario = Usuario(
            email="migrada@test.local",
            nombre="Cuenta migrada",
            password_hash=None,
            rol="cliente",
            activo=True,
            estado_registro="aprobado",
            origen="wordpress",
            wordpress_id=123,
            requiere_migracion_password=True,
            reset_password_token_hash=hashlib.sha256(token_reset.encode()).hexdigest(),
            reset_password_expira_en=datetime.now(timezone.utc) + timedelta(hours=1),
        )
        db.add(usuario)
        db.commit()

    def override_get_db():
        with Session(engine) as db:
            yield db

    app.dependency_overrides[get_db] = override_get_db
    try:
        with TestClient(app) as client:
            response = client.post("/api/auth/restablecer-password", json={
                "token": token_reset,
                "password": "password-nueva",
                "confirmar_password": "password-nueva",
            })
            assert response.status_code == 200

            login = client.post("/api/auth/login", json={
                "email": "migrada@test.local",
                "password": "password-nueva",
            })
            assert login.status_code == 200

        with Session(engine) as db:
            usuario = db.query(Usuario).filter_by(email="migrada@test.local").one()
            assert usuario.requiere_migracion_password is False
            assert usuario.email_verificado is True
            assert usuario.reset_password_token_hash is None
    finally:
        app.dependency_overrides.clear()


def test_normaliza_vencimiento_en_horario_argentino_a_utc():
    zona_argentina = timezone(timedelta(hours=-3))
    vencimiento_argentino = datetime(2026, 9, 30, 18, 18, 40, tzinfo=zona_argentina)

    assert _fecha_en_utc(vencimiento_argentino) == datetime(
        2026, 9, 30, 21, 18, 40, tzinfo=timezone.utc,
    )
