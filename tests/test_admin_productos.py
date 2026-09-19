from decimal import Decimal

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
