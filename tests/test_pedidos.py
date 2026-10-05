from decimal import Decimal
from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from sqlalchemy import select

from tests.test_carrito import crear_producto
from app.models.reserva_stock import ReservaStock
from app.models.reserva_carrito import ReservaCarrito
from app.models.notificacion import Notificacion
from app.models.pedido import Pedido
from app.models.pedido_historico_wordpress import PedidoHistoricoWordpress, PedidoItemHistoricoWordpress
from app.repositories.reserva_stock_repository import reconciliar_reservas_enviadas


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

    reserva = client.put("/api/carrito/reserva", json={"items": [{"producto_id": producto.id, "talle": "1", "cantidad": 24}]})
    assert reserva.status_code == 200, reserva.text

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
    assert db.scalar(select(ReservaCarrito).where(ReservaCarrito.producto_id == producto.id)) is None
    aviso = db.scalar(select(Notificacion).where(
        Notificacion.pedido_id == pedido["id"],
        Notificacion.tipo == "reserva_pedido",
    ))
    assert aviso is not None
    assert aviso.email_destino == "ana@example.com"
    assert aviso.email_estado == "omitido"
    assert "quedaron reservadas" in aviso.mensaje
    assert "hasta la entrega" in aviso.mensaje


def test_pedido_confirmado_programa_envio_automatico_a_dux(client: TestClient, db: Session, monkeypatch):
    producto = crear_producto(db, 1, precio_mayorista=Decimal("6000.00"), precio_24=Decimal("5000.00"))
    db.commit()
    pedidos_enviados = []

    monkeypatch.setattr(
        "app.api.routers.pedidosRouter.envio_automatico_dux_habilitado",
        lambda: True,
    )
    monkeypatch.setattr(
        "app.api.routers.pedidosRouter.enviar_pedido_dux_en_segundo_plano",
        lambda pedido_id: pedidos_enviados.append(pedido_id),
    )

    response = client.post("/api/pedidos/", json=pedido_payload(producto.id))

    assert response.status_code == 201
    assert pedidos_enviados == [response.json()["id"]]


def test_pedido_permite_compra_por_unidad(
    client: TestClient,
    db: Session,
):
    producto = crear_producto(db, 1)
    db.commit()

    response = client.post(
        "/api/pedidos/",
        json=pedido_payload(producto.id, cantidad=1),
    )

    assert response.status_code == 201, response.text
    assert response.json()["cantidad_unidades"] == 1


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


def test_admin_gestiona_estado_de_pedido_historico_wordpress(client: TestClient, db: Session, monkeypatch):
    emails = []
    monkeypatch.setattr(
        "app.services.notificacion_service._enviar_email",
        lambda destino, asunto, contenido: (emails.append((destino, asunto, contenido)) or ("enviado", None)),
    )
    historico = PedidoHistoricoWordpress(
        wordpress_id=7001, numero="7001", wordpress_customer_id=10,
        estado="completed", total=Decimal("12500"),
        facturacion={"first_name": "María", "last_name": "Pérez", "email": "maria@test.local", "phone": "3415550000"},
        envio={"address_1": "Calle Histórica 10", "city": "Rosario", "state": "Santa Fe"},
        creado_en_wordpress=datetime.now(timezone.utc),
    )
    historico.items.append(PedidoItemHistoricoWordpress(
        wordpress_id=7101, wordpress_product_id=50, producto_id=None,
        nombre="Pijama histórico", sku="WP-50", cantidad=2,
        subtotal=Decimal("12500"), total=Decimal("12500"), impuesto_total=0,
        precio_unitario=Decimal("6250"), metadatos=[{"display_key": "Talle", "display_value": "4"}],
    ))
    db.add(historico)
    db.commit()

    response = client.get("/api/admin/pedidos/", params={"origen": "wordpress"})
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["total"] == 1
    assert data["items"][0]["codigo"] == "WP-7001"
    assert data["items"][0]["origen"] == "wordpress"
    assert data["items"][0]["solo_lectura"] is False
    assert data["items"][0]["estado"] == "confirmado"
    assert data["items"][0]["estado_original"] == "completed"
    assert data["items"][0]["items"][0]["talle"] == "4"

    actualizado = client.patch(
        f"/api/admin/pedidos/{historico.id}/estado",
        json={"estado": "contactado", "origen": "wordpress"},
    )
    assert actualizado.status_code == 200, actualizado.text
    assert actualizado.json()["estado"] == "contactado"
    db.refresh(historico)
    assert historico.estado == "completed"
    assert historico.estado_gestion == "contactado"
    assert len(emails) == 0

    confirmado = client.patch(
        f"/api/admin/pedidos/{historico.id}/estado",
        json={"estado": "confirmado", "origen": "wordpress"},
    )
    assert confirmado.status_code == 200
    assert len(emails) == 1
    assert emails[0][0] == "maria@test.local"
    assert "WP-7001" in emails[0][1]
    assert "Completado" in emails[0][2]
    assert "Hola María Pérez" in emails[0][2]

    repetido = client.patch(
        f"/api/admin/pedidos/{historico.id}/estado",
        json={"estado": "confirmado", "origen": "wordpress"},
    )
    assert repetido.status_code == 200
    assert len(emails) == 1


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


def test_pedido_rechaza_suma_de_talles_superior_al_stock_total(
    client: TestClient,
    db: Session,
):
    from app.models.stock_talle_producto import StockTalleProducto

    producto = crear_producto(db, 2)
    producto.stocks[0].stock_real = 5
    producto.stocks[0].stock_disponible = 5
    producto.stocks_talles[0].cantidad = 5
    producto.stocks_talles.append(StockTalleProducto(talle="2", cantidad=5))
    db.commit()
    payload = pedido_payload(producto.id, cantidad=3)
    payload["items"] = [
        {"producto_id": producto.id, "talle": "1", "cantidad": 3},
        {"producto_id": producto.id, "talle": "2", "cantidad": 3},
    ]

    response = client.post("/api/pedidos/", json=payload)

    assert response.status_code == 400
    assert "5.00 unidades disponibles" in response.json()["detail"]
    assert db.scalar(select(Pedido.id)) is None


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


def test_admin_ordena_pedidos_por_total(client: TestClient, db: Session):
    base = dict(
        usuario_id=None, estado="pendiente", cliente_nombre="Cliente",
        cliente_telefono="3410000000", provincia="Santa Fe", localidad="Rosario",
        direccion="Calle 123", cantidad_productos_diferentes=1, cantidad_unidades=1,
        aplica_precio_24_productos=False, subtotal_sin_descuento=Decimal("1"),
        descuento_aplicado=Decimal("0"),
    )
    db.add_all([
        Pedido(codigo="PUP-TOTAL-BAJO", total=Decimal("100"), **base),
        Pedido(codigo="PUP-TOTAL-ALTO", total=Decimal("900"), **base),
    ])
    db.commit()

    mayor = client.get("/api/admin/pedidos/", params={"origen": "tienda", "orden": "total_desc"})
    menor = client.get("/api/admin/pedidos/", params={"origen": "tienda", "orden": "total_asc"})

    assert mayor.status_code == 200, mayor.text
    assert mayor.json()["items"][0]["codigo"] == "PUP-TOTAL-ALTO"
    assert menor.status_code == 200, menor.text
    assert menor.json()["items"][0]["codigo"] == "PUP-TOTAL-BAJO"


def test_reserva_enviada_espera_a_que_dux_impacte_el_pedido(db, monkeypatch):
    from app.core.config import settings

    producto = crear_producto(db, 70)
    ahora = datetime.now(timezone.utc)
    base = dict(
        estado="pendiente",
        cliente_nombre="Cliente",
        cliente_telefono="3410000000",
        provincia="Santa Fe",
        localidad="Rosario",
        direccion="Calle 123",
        cantidad_productos_diferentes=1,
        cantidad_unidades=3,
        aplica_precio_24_productos=False,
        subtotal_sin_descuento=Decimal("300"),
        descuento_aplicado=Decimal("0"),
        total=Decimal("300"),
        estado_sync_dux="enviado",
    )
    antiguo = Pedido(
        codigo="PUP-DUX-ANTIGUO",
        sincronizado_dux_en=ahora - timedelta(minutes=11),
        **base,
    )
    reciente = Pedido(
        codigo="PUP-DUX-RECIENTE",
        sincronizado_dux_en=ahora - timedelta(minutes=2),
        **base,
    )
    antiguo.reservas_stock.append(ReservaStock(
        producto_id=producto.id,
        talle="1",
        cantidad=3,
        estado="enviada_dux",
    ))
    reciente.reservas_stock.append(ReservaStock(
        producto_id=producto.id,
        talle="1",
        cantidad=2,
        estado="enviada_dux",
    ))
    db.add_all([antiguo, reciente])
    db.commit()
    monkeypatch.setattr(settings, "DUX_RECONCILIACION_RESERVA_MINUTOS", 10)

    reconciliadas = reconciliar_reservas_enviadas(db)
    db.commit()
    db.refresh(antiguo.reservas_stock[0])
    db.refresh(reciente.reservas_stock[0])
    db.refresh(producto.stocks_talles[0])

    assert reconciliadas == 1
    assert antiguo.reservas_stock[0].estado == "reconciliada"
    assert reciente.reservas_stock[0].estado == "enviada_dux"
    assert producto.stocks_talles[0].cantidad == 97
