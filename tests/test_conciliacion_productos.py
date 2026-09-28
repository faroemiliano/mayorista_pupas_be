from sqlalchemy import select

from app.models.migracion_woocommerce import MigracionWooCommerce
from app.models.producto import Producto
from app.services.conciliacion_productos_service import aplicar_coincidencias_seguras, conciliar_productos


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
