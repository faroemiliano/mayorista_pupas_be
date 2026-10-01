from decimal import Decimal
from datetime import datetime, timezone

from app.models.pedido_historico_wordpress import PedidoHistoricoWordpress, PedidoItemHistoricoWordpress
from app.models.precio_producto import PrecioProducto
from app.models.producto import Producto
from app.models.stock_producto import StockProducto
from app.models.stock_talle_producto import StockTalleProducto


def crear_producto(db_session, numero: int) -> Producto:
    producto = Producto(
        dux_codigo=f"A-{numero:03}",
        nombre=f"Analítica {numero:03}",
        slug=f"analitica-{numero:03}",
        habilitado=True,
    )
    producto.precios.append(
        PrecioProducto(dux_id_lista=4710, nombre_lista="Mayorista", precio=Decimal("2000"))
    )
    producto.stocks.append(
        StockProducto(
            dux_id_deposito=1,
            nombre_deposito="Central",
            stock_real=50,
            stock_reservado=0,
            stock_disponible=50,
        )
    )
    producto.stocks_talles.append(StockTalleProducto(talle=1, cantidad=50))
    db_session.add(producto)
    db_session.commit()
    db_session.refresh(producto)
    return producto


def test_analitica_clasifica_productos_vendidos_y_sin_ventas(client, db):
    vendido = crear_producto(db, 1)
    sin_ventas = crear_producto(db, 2)
    pedido = client.post(
        "/api/pedidos/",
        json={
            "cliente_nombre": "Cliente",
            "cliente_telefono": "3410000000",
            "provincia": "Santa Fe",
            "localidad": "Rosario",
            "direccion": "Calle 123",
            "items": [{"producto_id": vendido.id, "cantidad": 50}],
        },
    )
    assert pedido.status_code == 201

    response = client.get("/api/admin/productos/analitica?dias=30&limit=10")
    assert response.status_code == 200
    data = response.json()
    assert data["origen"] == "pedidos_tienda"
    assert data["resumen"]["unidades_vendidas"] == 50
    assert data["mas_vendidos"][0]["producto_id"] == vendido.id
    assert data["sin_ventas"][0]["producto_id"] == sin_ventas.id
    assert data["agrupacion"] == "dia"
    assert data["serie_ventas"][-1]["pedidos"] == 1
    assert data["serie_ventas"][-1]["unidades"] == 50
    assert Decimal(data["serie_ventas"][-1]["importe"]) > 0


def test_analitica_permite_agrupar_ventas_por_semana(client):
    response = client.get("/api/admin/productos/analitica?dias=90&agrupacion=semana")
    assert response.status_code == 200
    data = response.json()
    assert data["agrupacion"] == "semana"
    assert len(data["serie_ventas"]) >= 12

    invalida = client.get("/api/admin/productos/analitica?agrupacion=trimestre")
    assert invalida.status_code == 422


def test_analitica_no_cuenta_pedidos_cancelados(client, db):
    producto = crear_producto(db, 3)
    pedido = client.post(
        "/api/pedidos/",
        json={
            "cliente_nombre": "Cliente",
            "cliente_telefono": "3410000000",
            "provincia": "Santa Fe",
            "localidad": "Rosario",
            "direccion": "Calle 123",
            "items": [{"producto_id": producto.id, "cantidad": 50}],
        },
    ).json()
    response = client.patch(
        f"/api/admin/pedidos/{pedido['id']}/estado",
        json={"estado": "cancelado"},
    )
    assert response.status_code == 200

    data = client.get("/api/admin/productos/analitica").json()
    assert data["resumen"]["unidades_vendidas"] == 0
    assert data["resumen"]["productos_con_ventas"] == 0


def test_analitica_incluye_historial_wordpress(client, db):
    producto = crear_producto(db, 30)
    pedido = PedidoHistoricoWordpress(
        wordpress_id=9001,
        numero="9001",
        wordpress_customer_id=0,
        estado="completed",
        total=Decimal("6000"),
        creado_en_wordpress=datetime.now(timezone.utc),
    )
    pedido.items.append(PedidoItemHistoricoWordpress(
        wordpress_id=9101,
        wordpress_product_id=123,
        producto_id=producto.id,
        nombre=producto.nombre,
        cantidad=3,
        subtotal=Decimal("6000"),
        total=Decimal("6000"),
        impuesto_total=0,
        precio_unitario=Decimal("2000"),
    ))
    db.add(pedido)
    db.commit()

    data = client.get("/api/admin/productos/analitica?dias=30&limit=10").json()
    assert data["resumen"]["unidades_vendidas"] == 3
    assert data["resumen"]["productos_con_ventas"] == 1
    assert data["mas_vendidos"][0]["producto_id"] == producto.id
    assert sum(punto["pedidos"] for punto in data["serie_ventas"]) == 1
    assert sum(punto["unidades"] for punto in data["serie_ventas"]) == 3


def test_admin_puede_ocultar_producto_solo_en_la_tienda(client, db):
    producto = crear_producto(db, 4)
    response = client.patch(
        f"/api/admin/productos/{producto.id}/visibilidad",
        json={"visible": False},
    )
    assert response.status_code == 200
    assert response.json()["visible_tienda"] is False

    catalogo = client.get("/api/productos/?solo_habilitados=true")
    assert catalogo.status_code == 200
    assert catalogo.json()["total"] == 0

    administracion = client.get("/api/productos/?solo_habilitados=false")
    assert administracion.json()["total"] == 1
    assert administracion.json()["items"][0]["visible_tienda"] is False


def test_admin_crea_producto_web_con_talles_y_precios(client):
    response = client.post("/api/admin/productos/", json={
        "codigo": "WEB-NUEVO-001",
        "nombre": "Producto nuevo web",
        "descripcion": "Creado desde administración.",
        "categoria_id": None,
        "subcategoria_id": None,
        "marca_id": None,
        "precio_mayorista": "1000.00",
        "precio_24_productos": "900.00",
        "cantidad_unidades_por_bulto": 6,
        "talles": [{"talle": "S", "cantidad": 2}, {"talle": "M", "cantidad": 4}],
        "habilitado": True,
        "visible_tienda": True,
    })

    assert response.status_code == 201, response.text


def test_admin_distribuye_stock_dux_entre_talles(client, db):
    producto = crear_producto(db, 9)
    response = client.post(f"/api/admin/productos/{producto.id}/stock-talles", json={
        "talles": [{"talle": talle, "cantidad": 10} for talle in range(1, 6)]
    })
    assert response.status_code == 200, response.text
    assert response.json()["total_distribuido"] == 50

    exceso = client.post(f"/api/admin/productos/{producto.id}/stock-talles", json={
        "talles": [{"talle": talle, "cantidad": 11} for talle in range(1, 6)]
    })
    assert exceso.status_code == 422

    reemplazo = client.post(f"/api/admin/productos/{producto.id}/stock-talles", json={
        "talles": [{"talle": "3", "cantidad": 5}]
    })
    assert reemplazo.status_code == 200, reemplazo.text
    db.expire_all()
    actualizado = db.get(Producto, producto.id)
    assert [(fila.talle, fila.cantidad) for fila in actualizado.stocks_talles] == [("3", 5)]
