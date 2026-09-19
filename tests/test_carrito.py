from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.precio_producto import PrecioProducto
from app.models.producto import Producto
from app.models.stock_producto import StockProducto
from app.models.stock_talle_producto import StockTalleProducto


def crear_producto(
    db: Session,
    numero: int,
    precio_mayorista: Decimal = Decimal("100.00"),
    precio_24: Decimal = Decimal("80.00"),
    habilitado: bool = True,
) -> Producto:
    producto = Producto(
        dux_codigo=f"C-{numero:03}",
        nombre=f"Producto {numero:03}",
        slug=f"producto-{numero:03}",
        habilitado=habilitado,
    )
    producto.precios.extend([
        PrecioProducto(
            dux_id_lista=4710,
            nombre_lista="MAYORISTA",
            precio=precio_mayorista,
        ),
        PrecioProducto(
            dux_id_lista=43406,
            nombre_lista="24 PRODUCTOS",
            precio=precio_24,
        ),
    ])
    producto.stocks.append(
        StockProducto(
            dux_id_deposito=1,
            nombre_deposito="Central",
            stock_real=100,
            stock_reservado=0,
            stock_disponible=100,
        )
    )
    producto.stocks_talles.append(StockTalleProducto(talle=1, cantidad=100))
    db.add(producto)
    db.flush()

    return producto


def test_carrito_usa_precio_mayorista_antes_de_24(
    client: TestClient,
    db: Session,
):
    producto = crear_producto(db, 1)
    db.commit()

    response = client.post(
        "/api/carrito/calcular",
        json={
            "items": [
                {
                    "producto_id": producto.id,
                    "cantidad": 3,
                }
            ]
        },
    )

    assert response.status_code == 200

    carrito = response.json()

    assert carrito[
        "cantidad_productos_diferentes"
    ] == 1
    assert carrito["cantidad_unidades"] == 3
    assert carrito["compra_minima_unidades"] == 6
    assert carrito["faltantes_para_compra_minima"] == 3
    assert carrito["cumple_compra_minima"] is False
    assert carrito[
        "aplica_precio_24_productos"
    ] is False
    assert carrito[
        "faltantes_para_precio_24"
    ] == 21
    assert carrito["items"][0][
        "precio_unitario"
    ] == "100.00"
    assert carrito["total"] == "300.00"
    assert carrito["subtotal_sin_descuento"] == "300.00"
    assert carrito["descuento_aplicado"] == "0.00"


def test_carrito_aplica_precio_especial_con_24_unidades(
    client: TestClient,
    db: Session,
):
    producto = crear_producto(db, 1)
    db.commit()

    response = client.post(
        "/api/carrito/calcular",
        json={
            "items": [
                {
                    "producto_id": producto.id,
                    "cantidad": 24,
                }
            ]
        },
    )

    assert response.status_code == 200

    carrito = response.json()

    assert carrito[
        "cantidad_productos_diferentes"
    ] == 1
    assert carrito["cantidad_unidades"] == 24
    assert carrito[
        "aplica_precio_24_productos"
    ] is True
    assert carrito[
        "faltantes_para_precio_24"
    ] == 0
    assert all(
        item["precio_unitario"] == "80.00"
        for item in carrito["items"]
    )
    assert carrito["total"] == "1920.00"
    assert carrito["subtotal_sin_descuento"] == "2400.00"
    assert carrito["descuento_aplicado"] == "480.00"
    assert carrito["items"][0]["precio_mayorista"] == "100.00"
    assert carrito["items"][0]["descuento_aplicado"] == "480.00"


def test_carrito_consolida_lineas_repetidas(
    client: TestClient,
    db: Session,
):
    producto = crear_producto(db, 1)
    db.commit()

    response = client.post(
        "/api/carrito/calcular",
        json={
            "items": [
                {
                    "producto_id": producto.id,
                    "cantidad": 2,
                },
                {
                    "producto_id": producto.id,
                    "cantidad": 3,
                },
            ]
        },
    )

    carrito = response.json()

    assert response.status_code == 200
    assert len(carrito["items"]) == 1
    assert carrito["items"][0]["cantidad"] == 5
    assert carrito[
        "cantidad_productos_diferentes"
    ] == 1
    assert carrito["total"] == "500.00"


def test_carrito_mantiene_mayorista_si_precio_24_es_cero(
    client: TestClient,
    db: Session,
):
    productos = [
        crear_producto(
            db,
            numero,
            precio_24=(
                Decimal("0.00")
                if numero == 1
                else Decimal("80.00")
            ),
        )
        for numero in range(1, 25)
    ]
    db.commit()

    response = client.post(
        "/api/carrito/calcular",
        json={
            "items": [
                {
                    "producto_id": producto.id,
                    "cantidad": 1,
                }
                for producto in productos
            ]
        },
    )

    carrito = response.json()

    assert response.status_code == 200
    assert carrito["items"][0][
        "precio_unitario"
    ] == "100.00"
    assert carrito["total"] == "1940.00"


def test_carrito_rechaza_producto_no_disponible(
    client: TestClient,
    db: Session,
):
    producto = crear_producto(
        db,
        1,
        habilitado=False,
    )
    db.commit()

    response = client.post(
        "/api/carrito/calcular",
        json={
            "items": [
                {
                    "producto_id": producto.id,
                    "cantidad": 1,
                }
            ]
        },
    )

    assert response.status_code == 400
    assert "no habilitados" in response.json()[
        "detail"
    ]


def test_carrito_valida_items_y_cantidades(
    client: TestClient,
):
    assert client.post(
        "/api/carrito/calcular",
        json={"items": []},
    ).status_code == 422


def test_carrito_rechaza_cantidad_superior_al_stock(
    client: TestClient,
    db: Session,
):
    producto = crear_producto(db, 1)
    db.commit()

    response = client.post(
        "/api/carrito/calcular",
        json={
            "items": [
                {
                    "producto_id": producto.id,
                    "cantidad": 101,
                }
            ]
        },
    )

    assert response.status_code == 400
    assert "talle 1" in (
        response.json()["detail"]
    )


def test_carrito_separa_talles_y_suma_unidades_del_producto(client: TestClient, db: Session):
    producto = crear_producto(db, 8)
    producto.stocks_talles[0].cantidad = 50
    producto.stocks_talles.append(StockTalleProducto(talle=2, cantidad=50))
    db.commit()

    response = client.post("/api/carrito/calcular", json={"items": [
        {"producto_id": producto.id, "talle": 1, "cantidad": 2},
        {"producto_id": producto.id, "talle": 2, "cantidad": 4},
    ]})

    assert response.status_code == 200, response.text
    data = response.json()
    assert data["cantidad_productos_diferentes"] == 1
    assert data["cantidad_unidades"] == 6
    assert data["cumple_compra_minima"] is True
    assert {(item["talle"], item["cantidad"]) for item in data["items"]} == {(1, 2), (2, 4)}

    assert client.post(
        "/api/carrito/calcular",
        json={
            "items": [
                {
                    "producto_id": 1,
                    "cantidad": 0,
                }
            ]
        },
    ).status_code == 422
