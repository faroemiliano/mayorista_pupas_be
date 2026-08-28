from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from tests.test_carrito import crear_producto


def pedido_payload(producto_id: int, cantidad: int = 24) -> dict:
    return {
        "cliente_nombre": "Ana Pérez",
        "cliente_telefono": "1155551234",
        "cliente_email": "ana@example.com",
        "provincia": "Buenos Aires",
        "localidad": "Morón",
        "direccion": "Calle 123",
        "observaciones": "Entregar por la tarde",
        "items": [
            {
                "producto_id": producto_id,
                "cantidad": cantidad,
            }
        ],
    }


def test_crear_pedido_guarda_totales_e_items(
    client: TestClient,
    db: Session,
):
    producto = crear_producto(
        db,
        1,
        precio_mayorista=Decimal("6000.00"),
        precio_24=Decimal("5000.00"),
    )
    db.commit()

    response = client.post(
        "/api/pedidos/",
        json=pedido_payload(producto.id),
    )

    assert response.status_code == 201, response.text
    pedido = response.json()
    assert pedido["codigo"].startswith("PUP-")
    assert pedido["estado"] == "pendiente"
    assert pedido["cantidad_unidades"] == 24
    assert pedido["subtotal_sin_descuento"] == "144000.00"
    assert pedido["descuento_aplicado"] == "24000.00"
    assert pedido["total"] == "120000.00"
    assert pedido["items"][0]["producto_nombre"] == "Producto 001"

    consulta = client.get(
        f"/api/pedidos/{pedido['codigo']}"
    )
    assert consulta.status_code == 200


def test_pedido_rechaza_compra_inferior_al_minimo(
    client: TestClient,
    db: Session,
):
    producto = crear_producto(db, 1)
    db.commit()

    response = client.post(
        "/api/pedidos/",
        json=pedido_payload(producto.id, cantidad=1),
    )

    assert response.status_code == 400
    assert "compra mínima" in response.json()["detail"]


def test_admin_lista_y_actualiza_estado_del_pedido(
    client: TestClient,
    db: Session,
):
    producto = crear_producto(
        db,
        1,
        precio_mayorista=Decimal("6000.00"),
        precio_24=Decimal("5000.00"),
    )
    db.commit()
    pedido = client.post(
        "/api/pedidos/",
        json=pedido_payload(producto.id),
    ).json()

    listado = client.get(
        "/api/admin/pedidos/",
        params={"estado": "pendiente"},
    )
    assert listado.status_code == 200
    assert listado.json()["total"] == 1

    actualizado = client.patch(
        f"/api/admin/pedidos/{pedido['id']}/estado",
        json={"estado": "confirmado"},
    )
    assert actualizado.status_code == 200
    assert actualizado.json()["estado"] == "confirmado"


def test_mis_pedidos_filtra_por_usuario(client: TestClient, db: Session):
    from app.models.pedido import Pedido

    producto = crear_producto(db, 1, precio_mayorista=Decimal("6000.00"), precio_24=Decimal("5000.00"))
    db.commit()
    propio = client.post("/api/pedidos/", json=pedido_payload(producto.id)).json()
    db.add(Pedido(
        usuario_id=999, codigo="PUP-AJENO", estado="pendiente",
        cliente_nombre="Otro cliente", cliente_telefono="11111111",
        provincia="Santa Fe", localidad="Rosario", direccion="Otra calle 123",
        cantidad_productos_diferentes=1, cantidad_unidades=1,
        aplica_precio_24_productos=False, subtotal_sin_descuento=Decimal("6000"),
        descuento_aplicado=Decimal("0"), total=Decimal("6000"),
    ))
    db.commit()

    response = client.get("/api/pedidos/mios")
    assert response.status_code == 200
    assert response.json()["total"] == 1
    assert response.json()["items"][0]["codigo"] == propio["codigo"]
