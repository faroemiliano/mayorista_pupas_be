import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.security import get_usuario_opcional, verificar_password
from app.database.session import get_db
from app.main import app
from app.models.usuario import Usuario


@pytest.mark.parametrize("rol", ["admin", "admin_tecnico", "admin_operativo"])
def test_todos_los_roles_admin_pueden_asignar_password_temporal(engine, rol):
    with Session(engine) as db:
        cliente = Usuario(
            email=f"cliente-{rol}@test.local",
            nombre="Cliente",
            apellido="Prueba",
            rol="cliente",
            activo=True,
            estado_registro="aprobado",
            requiere_migracion_password=True,
            reset_password_token_hash="token-anterior",
        )
        db.add(cliente)
        db.commit()
        cliente_id = cliente.id

    def override_get_db():
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_usuario_opcional] = lambda: Usuario(
        id=99,
        email=f"{rol}@test.local",
        nombre="Administrador",
        apellido="",
        rol=rol,
        activo=True,
    )
    try:
        with TestClient(app) as admin_client:
            response = admin_client.patch(
                f"/api/admin/usuarios/{cliente_id}/password-temporal",
                json={
                    "password_nueva": "password-temporal",
                    "confirmar_password": "password-temporal",
                },
            )
        assert response.status_code == 200, response.text
        with Session(engine) as db:
            actualizado = db.get(Usuario, cliente_id)
            assert actualizado is not None
            assert verificar_password("password-temporal", actualizado.password_hash)
            assert actualizado.requiere_migracion_password is False
            assert actualizado.email_verificado is True
            assert actualizado.reset_password_token_hash is None
    finally:
        app.dependency_overrides.clear()


def test_admin_no_puede_cambiar_password_de_otro_admin(client, db):
    administrador = Usuario(
        email="otro-admin@test.local",
        nombre="Otro admin",
        apellido="",
        rol="admin",
        activo=True,
        estado_registro="aprobado",
    )
    db.add(administrador)
    db.commit()

    response = client.patch(
        f"/api/admin/usuarios/{administrador.id}/password-temporal",
        json={
            "password_nueva": "password-temporal",
            "confirmar_password": "password-temporal",
        },
    )

    assert response.status_code == 404


def test_password_temporal_requiere_confirmacion_coincidente(client, db):
    cliente = Usuario(
        email="cliente-password@test.local",
        nombre="Cliente",
        apellido="",
        rol="cliente",
        activo=True,
        estado_registro="aprobado",
    )
    db.add(cliente)
    db.commit()

    response = client.patch(
        f"/api/admin/usuarios/{cliente.id}/password-temporal",
        json={
            "password_nueva": "password-temporal",
            "confirmar_password": "otra-password",
        },
    )

    assert response.status_code == 422
