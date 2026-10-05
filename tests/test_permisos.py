def test_visitante_no_puede_usar_carrito(public_client):
    response = public_client.post("/api/carrito/calcular", json={"items": []})
    assert response.status_code == 401


def test_visitante_no_puede_entrar_al_panel(public_client):
    assert public_client.get("/api/admin/pedidos/").status_code == 401
    assert public_client.get("/api/admin/productos/analitica").status_code == 401
    assert public_client.patch("/api/admin/pedidos/1/estado", json={"estado":"cancelado"}).status_code == 401


def test_visitante_no_puede_ver_mis_pedidos(public_client):
    assert public_client.get("/api/pedidos/mios").status_code == 401


def test_admin_operativo_no_accede_a_analitica_migracion_ni_configuracion(engine):
    from fastapi.testclient import TestClient
    from app.core.security import get_usuario_opcional
    from app.database.session import get_db
    from app.main import app
    from app.models.usuario import Usuario
    from sqlalchemy.orm import Session

    def override_get_db():
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_usuario_opcional] = lambda: Usuario(
        id=2, email="operativa@test.local", nombre="Operativa", rol="admin_operativo", activo=True,
    )
    try:
        with TestClient(app) as operativa:
            assert operativa.get("/api/admin/pedidos/").status_code == 200
            assert operativa.get("/api/admin/productos/analitica").status_code == 403
            assert operativa.get("/api/admin/migracion-wordpress/resumen").status_code == 403
            assert operativa.patch("/api/admin/configuracion/dux/modo", json={"habilitado": True}).status_code == 403
    finally:
        app.dependency_overrides.clear()


def test_registro_guarda_perfil_comercial(public_client, db):
    from app.models.usuario import Usuario
    from sqlalchemy import select

    response = public_client.post("/api/auth/registro", json={
        "nombre": "Tienda Prueba",
        "email": "tienda.prueba@test.local",
        "telefono": "3415551234",
        "password": "password-seguro",
        "confirmar_password": "password-seguro",
        "provincia": "Santa Fe",
        "localidad_partido": "Rosario",
        "domicilio": "Calle Prueba 123",
        "canal_venta": "ambos",
        "tienda_online_url": "https://tienda.example.com",
    })

    assert response.status_code == 201, response.text
    usuario = db.scalar(select(Usuario).where(Usuario.email == "tienda.prueba@test.local"))
    assert usuario is not None
    assert usuario.provincia == "Santa Fe"
    assert usuario.localidad_partido == "Rosario"
    assert usuario.domicilio == "Calle Prueba 123"
    assert usuario.canal_venta == "ambos"
    assert usuario.tienda_online_url == "https://tienda.example.com"


def test_admin_conserva_historial_de_registros(client, db):
    from app.models.usuario import Usuario

    for index, estado in enumerate(("pendiente", "aprobado", "rechazado"), start=1):
        db.add(Usuario(email=f"cliente{index}@test.local", nombre=f"Cliente {index}", rol="cliente", estado_registro=estado))
    db.commit()

    response = client.get("/api/admin/usuarios/")
    assert response.status_code == 200
    assert {usuario["estado_registro"] for usuario in response.json()} == {"pendiente", "aprobado", "rechazado"}


def test_visitante_no_recibe_precios(public_client, db):
    from app.models.producto import Producto
    from app.models.precio_producto import PrecioProducto
    producto = Producto(dux_codigo="PUBLICO", nombre="Público", slug="publico", habilitado=True)
    producto.precios.append(PrecioProducto(dux_id_lista=4710, nombre_lista="Mayorista", precio=1000))
    db.add(producto)
    db.commit()
    response = public_client.get("/api/productos/")
    assert response.status_code == 200
    assert response.json()["items"][0]["precio_mayorista"] is None
