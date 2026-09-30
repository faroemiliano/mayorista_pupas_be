from datetime import datetime, timezone
from decimal import Decimal

import pytest
from sqlalchemy import select

from app.models.codigo_barra_producto import CodigoBarraProducto
from app.models.migracion_woocommerce import MigracionWooCommerce
from app.models.pedido import Pedido
from app.models.pedido_historico_wordpress import PedidoHistoricoWordpress, PedidoItemHistoricoWordpress
from app.models.pedido_item import PedidoItem
from app.models.precio_producto import PrecioProducto
from app.models.producto import Producto
from app.models.reserva_stock import ReservaStock
from app.models.stock_producto import StockProducto
from app.models.stock_talle_producto import StockTalleProducto
from app.services.conciliacion_productos_service import (
    aplicar_coincidencias_seguras,
    conciliar_productos,
    vincular_coincidencia_manual,
)


def test_clasifica_coincidencias_y_diferencias():
    wordpress = [
        {"id": 1, "name": "Pijama Luna", "sku": "A1", "_variaciones_completas": []},
        {"id": 2, "name": "Bikini Sol", "sku": "", "_variaciones_completas": []},
        {"id": 3, "name": "Producto exclusivo", "sku": "", "_variaciones_completas": []},
    ]
    dux = [
        {"cod_item": "A1", "item": "Otro nombre"},
        {"cod_item": "B2", "item": "Bikini Sol"},
        {"cod_item": "C3", "item": "Sólo Dux"},
    ]

    resultado = conciliar_productos(wordpress, dux)

    assert resultado["totales"] == {
        "wordpress": 3, "dux": 3, "coincidencias": 2,
        "dudosos": 0, "solo_wordpress": 1, "solo_dux": 1,
    }
    assert {item["criterio"] for item in resultado["coincidencias"]} == {"codigo", "nombre_exacto"}


def test_aplica_solo_coincidencias_seguras_y_es_repetible(db):
    producto = Producto(
        wordpress_id=10, origen="wordpress", dux_codigo="WP-10",
        nombre="Pijama Luna", slug="pijama-luna",
    )
    db.add_all([producto, MigracionWooCommerce(
        tipo="conciliacion", id_externo="productos-wordpress-dux", checksum="a" * 64,
        datos={"coincidencias": [{
            "wordpress_id": "10", "wordpress_nombre": "Pijama Luna",
            "dux_codigo": "A1", "dux_nombre": "Pijama Luna", "criterio": "codigo",
        }], "dudosos": [{"wordpress_id": "11"}]},
    )])
    db.commit()

    primera = aplicar_coincidencias_seguras(db)
    segunda = aplicar_coincidencias_seguras(db)
    db.refresh(producto)

    assert primera["vinculados"] == 1
    assert segunda["ya_vinculados"] == 1
    assert producto.dux_codigo == "A1"
    assert producto.origen == "wordpress_dux"
    assert producto.conciliacion_estado == "vinculado"
    assert db.scalar(select(Producto).where(Producto.wordpress_id == 11)) is None


def test_fusiona_duplicado_dux_y_reasigna_referencias_sin_perder_presentacion(db):
    wordpress = Producto(
        wordpress_id=10,
        origen="wordpress",
        dux_codigo="WP-10",
        nombre="Nombre comercial WordPress",
        slug="nombre-comercial-wordpress",
        descripcion="Descripción comercial",
        imagen_url="https://wordpress.test/producto.jpg",
    )
    wordpress.precios.append(
        PrecioProducto(dux_id_lista=4710, nombre_lista="WordPress temporal", precio=Decimal("100"))
    )
    wordpress.stocks.append(StockProducto(
        dux_id_deposito=-1,
        nombre_deposito="WordPress temporal",
        stock_real=3,
        stock_reservado=0,
        stock_disponible=3,
    ))
    wordpress.stocks_talles.append(
        StockTalleProducto(talle="M", cantidad=3, origen="wordpress")
    )
    wordpress.codigos_barra.append(CodigoBarraProducto(codigo="WP-BARRA"))

    duplicado_dux = Producto(
        origen="dux",
        dux_codigo="A1",
        nombre="Nombre interno Dux",
        slug="nombre-interno-dux-a1",
        descripcion="Descripción Dux",
        imagen_url="https://dux.test/producto.jpg",
    )
    duplicado_dux.precios.append(
        PrecioProducto(dux_id_lista=4710, nombre_lista="Mayorista Dux", precio=Decimal("250"))
    )
    duplicado_dux.stocks.append(StockProducto(
        dux_id_deposito=7,
        nombre_deposito="Central",
        stock_real=12,
        stock_reservado=2,
        stock_disponible=10,
        dux_id_det_item=700,
        codigo_barra_detalle="DET-A1-M",
        talle="M",
        color="Rosa",
    ))
    duplicado_dux.stocks_talles.append(
        StockTalleProducto(talle="M", cantidad=10, origen="dux")
    )
    duplicado_dux.codigos_barra.append(CodigoBarraProducto(codigo="DUX-BARRA"))
    db.add_all([wordpress, duplicado_dux])
    db.flush()
    wordpress_id = wordpress.id
    duplicado_id = duplicado_dux.id

    pedido = Pedido(
        codigo="PUP-MERGE",
        estado="pendiente",
        cliente_nombre="Cliente",
        cliente_telefono="3410000000",
        provincia="Santa Fe",
        localidad="Rosario",
        direccion="Calle 123",
        cantidad_productos_diferentes=2,
        cantidad_unidades=3,
        aplica_precio_24_productos=False,
        subtotal_sin_descuento=Decimal("750"),
        descuento_aplicado=Decimal("0"),
        total=Decimal("750"),
    )
    pedido.items.append(PedidoItem(
        producto_id=duplicado_id,
        dux_codigo="A1",
        producto_nombre="Nombre interno Dux",
        cantidad=2,
        talle="M",
        precio_mayorista=Decimal("250"),
        precio_unitario=Decimal("250"),
        subtotal_sin_descuento=Decimal("500"),
        descuento_aplicado=Decimal("0"),
        subtotal=Decimal("500"),
    ))
    pedido.reservas_stock.extend([
        ReservaStock(producto_id=wordpress_id, talle="M", cantidad=1, estado="activa"),
        ReservaStock(producto_id=duplicado_id, talle="M", cantidad=2, estado="activa"),
    ])

    historico = PedidoHistoricoWordpress(
        wordpress_id=900,
        numero="900",
        wordpress_customer_id=0,
        estado="completed",
        total=Decimal("250"),
        creado_en_wordpress=datetime.now(timezone.utc),
    )
    historico.items.append(PedidoItemHistoricoWordpress(
        wordpress_id=901,
        wordpress_product_id=999,
        wordpress_variation_id=0,
        producto_id=duplicado_id,
        nombre="Nombre interno Dux",
        sku="A1",
        cantidad=1,
        subtotal=Decimal("250"),
        total=Decimal("250"),
        impuesto_total=Decimal("0"),
    ))
    informe = MigracionWooCommerce(
        tipo="conciliacion",
        id_externo="productos-wordpress-dux",
        checksum="b" * 64,
        datos={
            "coincidencias": [{
                "wordpress_id": "10",
                "wordpress_nombre": "Nombre comercial WordPress",
                "dux_codigo": "A1",
                "dux_nombre": "Nombre interno Dux",
                "criterio": "codigo",
            }],
            "dudosos": [],
        },
    )
    db.add_all([pedido, historico, informe])
    db.commit()
    pedido_id = pedido.id

    primera = aplicar_coincidencias_seguras(db)
    segunda = aplicar_coincidencias_seguras(db)
    producto = db.get(Producto, wordpress_id)

    assert primera["vinculados"] == 1
    assert primera["fusionados"] == 1
    assert segunda["ya_vinculados"] == 1
    assert db.get(Producto, duplicado_id) is None
    assert producto.dux_codigo == "A1"
    assert producto.nombre == "Nombre comercial WordPress"
    assert producto.slug == "nombre-comercial-wordpress"
    assert producto.descripcion == "Descripción comercial"
    assert producto.imagen_url == "https://wordpress.test/producto.jpg"
    assert [(item.dux_id_lista, item.nombre_lista, item.precio) for item in producto.precios] == [
        (4710, "Mayorista Dux", Decimal("250.00"))
    ]
    assert [(item.dux_id_deposito, item.dux_id_det_item, item.stock_disponible) for item in producto.stocks] == [
        (7, 700, Decimal("10.00"))
    ]
    assert [(item.talle, item.cantidad, item.origen) for item in producto.stocks_talles] == [
        ("M", 3, "wordpress")
    ]
    assert [item.codigo for item in producto.codigos_barra] == ["DUX-BARRA"]
    assert db.scalar(select(PedidoItem).where(PedidoItem.pedido_id == pedido_id)).producto_id == wordpress_id
    reservas = list(db.scalars(select(ReservaStock).where(ReservaStock.pedido_id == pedido_id)).all())
    assert [(item.producto_id, item.talle, item.cantidad, item.estado) for item in reservas] == [
        (wordpress_id, "M", 3, "activa")
    ]
    assert db.scalar(
        select(PedidoItemHistoricoWordpress).where(PedidoItemHistoricoWordpress.pedido_id == historico.id)
    ).producto_id == wordpress_id


def test_vinculacion_manual_tambien_fusiona_producto_dux(db):
    wordpress = Producto(
        wordpress_id=20,
        origen="wordpress",
        dux_codigo="WP-20",
        nombre="Pijama comercial",
        slug="pijama-comercial",
    )
    duplicado_dux = Producto(
        origen="dux",
        dux_codigo="D20",
        nombre="Pijama Dux",
        slug="pijama-dux-d20",
    )
    duplicado_dux.stocks.append(StockProducto(
        dux_id_deposito=1,
        nombre_deposito="Central",
        stock_real=8,
        stock_reservado=0,
        stock_disponible=8,
    ))
    informe = MigracionWooCommerce(
        tipo="conciliacion",
        id_externo="productos-wordpress-dux",
        checksum="c" * 64,
        datos={
            "coincidencias": [],
            "dudosos": [],
            "solo_wordpress": [{"wordpress_id": "20", "wordpress_nombre": "Pijama comercial"}],
            "solo_dux": [{"dux_codigo": "D20", "dux_nombre": "Pijama Dux"}],
        },
    )
    db.add_all([wordpress, duplicado_dux, informe])
    db.commit()
    wordpress_id = wordpress.id
    duplicado_id = duplicado_dux.id

    vinculado = vincular_coincidencia_manual(db, 20, "D20")
    repetido = vincular_coincidencia_manual(db, 20, "D20")

    assert vinculado.id == wordpress_id
    assert repetido.id == wordpress_id
    assert vinculado.dux_codigo == "D20"
    assert vinculado.conciliacion_criterio == "manual"
    assert db.get(Producto, duplicado_id) is None
    assert int(vinculado.stocks[0].stock_disponible) == 8


def test_no_fusiona_codigo_dux_que_pertenece_a_otro_producto_wordpress(db):
    candidato = Producto(
        wordpress_id=30,
        origen="wordpress",
        dux_codigo="WP-30",
        nombre="Producto candidato",
        slug="producto-candidato",
    )
    ya_vinculado = Producto(
        wordpress_id=31,
        origen="wordpress_dux",
        dux_codigo="D30",
        nombre="Otro producto",
        slug="otro-producto",
        conciliacion_estado="vinculado",
    )
    informe = MigracionWooCommerce(
        tipo="conciliacion",
        id_externo="productos-wordpress-dux",
        checksum="d" * 64,
        datos={
            "coincidencias": [{
                "wordpress_id": "30",
                "dux_codigo": "D30",
                "criterio": "codigo",
            }],
            "dudosos": [],
        },
    )
    db.add_all([candidato, ya_vinculado, informe])
    db.commit()

    with pytest.raises(ValueError, match="códigos Dux ya asignados"):
        aplicar_coincidencias_seguras(db)

    db.refresh(candidato)
    db.refresh(ya_vinculado)
    assert candidato.dux_codigo == "WP-30"
    assert candidato.conciliacion_estado == "pendiente"
    assert ya_vinculado.dux_codigo == "D30"
    assert ya_vinculado.wordpress_id == 31
