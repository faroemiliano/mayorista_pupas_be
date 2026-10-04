from sqlalchemy import select

from app.models.migracion_woocommerce import MigracionWooCommerce
from app.models.usuario import Usuario
from app.models.usuario_wordpress import UsuarioWordpress
from app.services.conversion_clientes_wordpress_service import convertir_clientes_wordpress


def test_convierte_cliente_y_vincula_existente_sin_cambiar_rol(db):
    admin = Usuario(email="admin@test.com", nombre="Admin", apellido="", rol="admin", password_hash="hash", estado_registro="aprobado")
    db.add(admin)
    db.add_all([
        MigracionWooCommerce(tipo="cliente", id_externo="10", checksum="a" * 64, datos={
            "id": 10, "email": "cliente@test.com", "first_name": "Ana", "last_name": "Pérez",
            "date_created": "2023-05-01T10:00:00", "billing": {"phone": "123", "city": "Rosario", "state": "S", "address_1": "Calle 1"},
        }),
        MigracionWooCommerce(tipo="cliente", id_externo="20", checksum="b" * 64, datos={
            "id": 20, "email": "admin@test.com", "first_name": "No reemplazar", "billing": {},
        }),
    ])
    db.commit()

    resultado = convertir_clientes_wordpress(db)
    cliente = db.scalar(select(Usuario).where(Usuario.wordpress_id == 10))

    assert resultado["creados"] == 1
    assert resultado["vinculados"] == 1
    assert cliente.requiere_migracion_password is True
    assert cliente.estado_registro == "aprobado"
    assert cliente.domicilio == "Calle 1"
    assert admin.rol == "admin"
    assert admin.wordpress_id == 20
    assert admin.requiere_migracion_password is False
    assert db.query(UsuarioWordpress).count() == 2


def test_completa_nombre_y_apellido_de_cuenta_migrada_generica(db):
    usuario = Usuario(
        email="ana@test.com", nombre="Cliente", apellido="", rol="cliente",
        estado_registro="aprobado",
    )
    db.add(usuario)
    db.add(MigracionWooCommerce(tipo="cliente", id_externo="30", checksum="c" * 64, datos={
        "id": 30, "email": "ana@test.com", "first_name": "Ana", "last_name": "Pérez",
        "billing": {},
    }))
    db.commit()

    convertir_clientes_wordpress(db)
    db.refresh(usuario)

    assert usuario.nombre == "Ana"
    assert usuario.apellido == "Pérez"
