from sqlalchemy import select

from app.models.migracion_woocommerce import MigracionWooCommerce
from app.models.producto import Producto
from app.services.conversion_catalogo_wordpress_service import convertir_catalogo_wordpress


def test_convierte_producto_wordpress_sin_perder_variaciones(db):
    db.add_all([
        MigracionWooCommerce(tipo="categoria", id_externo="1", checksum="a" * 64, datos={"id": 1, "name": "Pijamas", "slug": "pijamas", "parent": 0}),
        MigracionWooCommerce(tipo="categoria", id_externo="2", checksum="b" * 64, datos={"id": 2, "name": "Invierno", "slug": "invierno", "parent": 1}),
        MigracionWooCommerce(tipo="producto", id_externo="10", checksum="c" * 64, datos={
            "id": 10, "name": "Pijama Luna", "slug": "pijama-luna", "status": "publish", "type": "variable",
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

    repeticion = convertir_catalogo_wordpress(db)
    db.refresh(producto)
    assert repeticion["actualizados"] == 1
    assert len(producto.precios) == 2
    assert len(producto.variaciones) == 2
    assert len(producto.imagenes) == 2
