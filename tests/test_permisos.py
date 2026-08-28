def test_visitante_no_puede_usar_carrito(public_client):
    response = public_client.post("/api/carrito/calcular", json={"items": []})
    assert response.status_code == 401


def test_visitante_no_puede_entrar_al_panel(public_client):
    assert public_client.get("/api/admin/pedidos/").status_code == 401
    assert public_client.get("/api/admin/productos/analitica").status_code == 401


def test_visitante_no_puede_ver_mis_pedidos(public_client):
    assert public_client.get("/api/pedidos/mios").status_code == 401


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
