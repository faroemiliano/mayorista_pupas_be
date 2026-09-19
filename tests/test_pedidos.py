from decimal import Decimal
from datetime import datetime, timezone

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from sqlalchemy import select

from tests.test_carrito import crear_producto
from app.models.reserva_stock import ReservaStock


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
        json=pedido_payload(producto.id, cantidad=5),
    )

    assert response.status_code == 400
    assert "compra mínima" in response.json()["detail"]


def test_pedido_permite_seis_prendas_sin_minimo_monetario(
    client: TestClient,
    db: Session,
):
    producto = crear_producto(db, 1, precio_mayorista=Decimal("100.00"))
    db.commit()

    response = client.post(
        "/api/pedidos/",
        json=pedido_payload(producto.id, cantidad=6),
    )

    assert response.status_code == 201, response.text
    assert response.json()["cantidad_unidades"] == 6
    assert response.json()["total"] == "600.00"


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


def test_crear_pedido_reserva_stock_y_evitar_sobreventa(
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

    primero = client.post(
        "/api/pedidos/",
        json=pedido_payload(producto.id, cantidad=80),
    )
    assert primero.status_code == 201, primero.text

    detalle = client.get(f"/api/productos/{producto.id}")
    assert detalle.status_code == 200
    assert detalle.json()["stock_disponible"] == "20.00"

    segundo = client.post(
        "/api/pedidos/",
        json=pedido_payload(producto.id, cantidad=21),
    )
    assert segundo.status_code == 400
    assert "20" in segundo.json()["detail"]


def test_cancelar_pedido_libera_reserva_local(
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

    cancelado = client.patch(
        f"/api/admin/pedidos/{pedido['id']}/estado",
        json={"estado": "cancelado"},
    )
    assert cancelado.status_code == 200

    detalle = client.get(f"/api/productos/{producto.id}")
    assert detalle.json()["stock_disponible"] == "100.00"
    reserva = db.scalar(
        select(ReservaStock).where(ReservaStock.pedido_id == pedido["id"])
    )
    db.refresh(reserva)
    assert reserva.estado == "liberada"
    assert reserva.liberada_en is not None


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


def test_pedido_cancelado_no_puede_enviarse_a_dux(client: TestClient, db: Session, monkeypatch):
    from app.core.config import settings

    producto = crear_producto(db, 1, precio_mayorista=Decimal("6000.00"), precio_24=Decimal("5000.00"))
    db.commit()
    pedido = client.post("/api/pedidos/", json=pedido_payload(producto.id)).json()
    cancelado = client.patch(f"/api/admin/pedidos/{pedido['id']}/estado", json={"estado":"cancelado"})
    assert cancelado.status_code == 200
    monkeypatch.setattr(settings, "DUX_ESCRITURA_HABILITADA", True)

    response = client.post(f"/api/admin/pedidos/{pedido['id']}/enviar-dux", json={"id_personal":1051689})
    assert response.status_code == 400
    assert "cancelado" in response.json()["detail"]


def test_nuevo_pedido_genera_notificacion_para_admin(client: TestClient, db: Session):
    producto = crear_producto(db, 1, precio_mayorista=Decimal("6000.00"), precio_24=Decimal("5000.00"))
    db.commit()
    pedido = client.post("/api/pedidos/", json=pedido_payload(producto.id))
    assert pedido.status_code == 201

    response = client.get("/api/notificaciones/admin")
    assert response.status_code == 200
    assert response.json()["no_leidas"] == 1
    assert response.json()["items"][0]["tipo"] == "pedido_nuevo"
    detalle = client.get(f"/api/admin/pedidos/{pedido.json()['id']}")
    assert detalle.status_code == 200
    assert detalle.json()["codigo"] == pedido.json()["codigo"]


def test_admin_filtra_pedidos_por_mes_y_cliente(client: TestClient, db: Session):
    from app.models.pedido import Pedido

    base = dict(
        usuario_id=None,
        estado="pendiente",
        cliente_telefono="3410000000",
        provincia="Santa Fe",
        localidad="Rosario",
        direccion="Calle 123",
        cantidad_productos_diferentes=1,
        cantidad_unidades=6,
        aplica_precio_24_productos=False,
        subtotal_sin_descuento=Decimal("6000"),
        descuento_aplicado=Decimal("0"),
        total=Decimal("6000"),
    )
    db.add_all([
        Pedido(codigo="PUP-OCTUBRE-ANA", cliente_nombre="Ana Pérez", cliente_email="ana@test.local", creado_en=datetime(2025, 10, 15, 15, tzinfo=timezone.utc), **base),
        Pedido(codigo="PUP-NOVIEMBRE-JUAN", cliente_nombre="Juan López", cliente_email="juan@test.local", creado_en=datetime(2025, 11, 2, 15, tzinfo=timezone.utc), **base),
    ])
    db.commit()

    response = client.get("/api/admin/pedidos/", params={
        "fecha_desde": "2025-10-01",
        "fecha_hasta": "2025-10-31",
        "buscar": "Ana",
    })

    assert response.status_code == 200, response.text
    assert response.json()["total"] == 1
    assert response.json()["items"][0]["codigo"] == "PUP-OCTUBRE-ANA"
