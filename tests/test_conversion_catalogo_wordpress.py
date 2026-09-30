from sqlalchemy import select
from datetime import datetime

from app.models.migracion_woocommerce import MigracionWooCommerce
from app.models.producto import Producto
from app.models.precio_producto import PrecioProducto
from app.models.stock_producto import StockProducto
from app.models.stock_talle_producto import StockTalleProducto
from app.services.conversion_catalogo_wordpress_service import convertir_catalogo_wordpress


def test_convierte_producto_wordpress_sin_perder_variaciones(db):
    db.add_all([
        MigracionWooCommerce(tipo="categoria", id_externo="1", checksum="a" * 64, datos={"id": 1, "name": "Pijamas", "slug": "pijamas", "parent": 0}),
        MigracionWooCommerce(tipo="categoria", id_externo="2", checksum="b" * 64, datos={"id": 2, "name": "Invierno", "slug": "invierno", "parent": 1}),
        MigracionWooCommerce(tipo="producto", id_externo="10", checksum="c" * 64, datos={
            "id": 10, "name": "Pijama Luna", "slug": "pijama-luna", "status": "publish", "type": "variable",
            "date_created_gmt": "2026-09-15T12:30:00",
            "description": "Descripción", "sku": "", "categories": [{"id": 2, "name": "Invierno"}],
            "images": [{"src": "https://example.com/1.jpg"}, {"src": "https://example.com/2.jpg"}],
            "_variaciones_completas": [
                {"id": 101, "sku": "", "price": "1200", "stock_quantity": 3, "stock_status": "instock", "status": "publish", "attributes": [{"name": "Talle", "option": "1"}]},
                {"id": 102, "sku": "", "price": "1200", "stock_quantity": 2, "stock_status": "instock", "status": "publish", "attributes": [{"name": "Talle", "option": "Kids"}]},
            ],
        }),
    ])
    db.commit()

    resultado = convertir_catalogo_wordpress(db)
    producto = db.scalar(select(Producto).where(Producto.wordpress_id == 10))

    assert resultado["creados"] == 1
    assert producto is not None
    assert producto.categoria.nombre == "Pijamas"
    assert producto.subcategoria.nombre == "Invierno"
    assert len(producto.variaciones) == 2
    assert producto.variaciones[1].atributos == {"Talle": "Kids"}
    assert [(item.talle, item.cantidad) for item in producto.stocks_talles] == [("1", 3), ("Kids", 2)]
    assert int(producto.stocks[0].stock_disponible) == 5
    assert len(producto.imagenes) == 2
    assert producto.creado_en.replace(tzinfo=None) == datetime(2026, 9, 15, 12, 30)

    repeticion = convertir_catalogo_wordpress(db)
    db.refresh(producto)
    assert repeticion["actualizados"] == 1
    assert len(producto.precios) == 2
    assert len(producto.variaciones) == 2
    assert len(producto.imagenes) == 2


def test_reconversion_wordpress_no_pisa_stock_ni_precios_dux_vinculados(db):
    datos = {
        "id": 20,
        "name": "Producto comercial",
        "slug": "producto-comercial",
        "status": "publish",
        "type": "variable",
        "price": "100",
        "categories": [],
        "images": [],
        "_variaciones_completas": [{
            "id": 201,
            "sku": "DUX-20",
            "price": "100",
            "stock_quantity": 99,
            "stock_status": "instock",
            "status": "publish",
            "attributes": [{"name": "Talle", "option": "M"}],
        }],
    }
    db.add(MigracionWooCommerce(
        tipo="producto",
        id_externo="20",
        checksum="d" * 64,
        datos=datos,
    ))
    producto = Producto(
        wordpress_id=20,
        origen="wordpress_dux",
        dux_codigo="DUX-20",
        nombre="Producto comercial",
        slug="producto-comercial",
        conciliacion_estado="vinculado",
    )
    producto.precios.append(PrecioProducto(
        dux_id_lista=4710,
        nombre_lista="MAYORISTA DUX",
        precio=250,
    ))
    producto.stocks.append(StockProducto(
        dux_id_deposito=2169,
        nombre_deposito="Depósito Dux",
        stock_real=7,
        stock_reservado=0,
        stock_disponible=7,
    ))
    producto.stocks_talles.append(StockTalleProducto(
        talle="M",
        cantidad=7,
        origen="dux",
    ))
    db.add(producto)
    db.commit()

    convertir_catalogo_wordpress(db)
    db.refresh(producto)

    assert producto.origen == "wordpress_dux"
    assert [(precio.nombre_lista, int(precio.precio)) for precio in producto.precios] == [
        ("MAYORISTA DUX", 250),
    ]
    assert [(stock.dux_id_deposito, int(stock.stock_disponible)) for stock in producto.stocks] == [
        (2169, 7),
    ]
    assert [(stock.talle, stock.cantidad, stock.origen) for stock in producto.stocks_talles] == [
        ("M", 7, "dux"),
    ]
