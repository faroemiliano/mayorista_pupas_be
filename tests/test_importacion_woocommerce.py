from app.core.security import verificar_password
from app.services.woocommerce_cliente_service import importar_cliente_woocommerce


def test_importa_un_cliente_woocommerce(monkeypatch, db):
    monkeypatch.setattr(
        "app.services.woocommerce_cliente_service.WooCommerceClient.buscar_cliente_por_email",
        lambda self, email: {
            "email": email,
            "first_name": "Emiliano",
            "last_name": "Faro",
            "username": "emiliano",
            "billing": {"phone": "1122334455", "address_1": "Calle 1", "address_2": "", "city": "CABA", "state": "C"},
            "shipping": {},
        },
    )
    usuario, creado, password = importar_cliente_woocommerce(db, "CLIENTE@EXAMPLE.COM")
    assert creado is True
    assert usuario.email == "cliente@example.com"
    assert usuario.estado_registro == "aprobado"
    assert usuario.telefono == "1122334455"
    assert password and verificar_password(password, usuario.password_hash)


def test_importacion_actualiza_sin_reemplazar_password_ni_rol(monkeypatch, db):
    from app.core.security import hashear_password
    from app.models.usuario import Usuario

    usuario = Usuario(email="admin@example.com", nombre="Anterior", rol="admin", password_hash=hashear_password("password-original"))
    db.add(usuario)
    db.commit()
    monkeypatch.setattr(
        "app.services.woocommerce_cliente_service.WooCommerceClient.buscar_cliente_por_email",
        lambda self, email: {"email": email, "first_name": "Nuevo", "last_name": "Nombre", "billing": {}, "shipping": {}},
    )
    actualizado, creado, password = importar_cliente_woocommerce(db, "admin@example.com")
    assert creado is False
    assert password is None
    assert actualizado.rol == "admin"
    assert verificar_password("password-original", actualizado.password_hash)
