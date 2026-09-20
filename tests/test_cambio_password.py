from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.security import crear_token, hashear_password
from app.database.session import get_db
from app.main import app
from app.models.usuario import Usuario


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
