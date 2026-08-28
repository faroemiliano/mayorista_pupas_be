from decimal import Decimal

from app.models.precio_producto import PrecioProducto
from app.models.producto import Producto
from app.models.stock_producto import StockProducto


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
