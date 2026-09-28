from app.models.migracion_woocommerce import MigracionWooCommerce
from app.services.migracion_woocommerce_service import importar_todos_productos


def test_importa_productos_con_variaciones(monkeypatch, db):
    productos = [
        {"id": 10, "name": "Variable", "type": "variable"},
        {"id": 11, "name": "Simple", "type": "simple"},
    ]
    monkeypatch.setattr(
        "app.services.migracion_woocommerce_service.WooCommerceClient.obtener_pagina",
        lambda self, recurso, pagina: (productos, 1),
    )
    monkeypatch.setattr(
        "app.services.migracion_woocommerce_service.WooCommerceClient.obtener_variaciones",
        lambda self, producto_id: [{"id": 101, "stock_quantity": 3}],
    )

    resultado = importar_todos_productos(db)

    assert resultado["creados"] == 2
    filas = db.query(MigracionWooCommerce).filter_by(tipo="producto").order_by(MigracionWooCommerce.id_externo).all()
    assert filas[0].datos["_variaciones_completas"][0]["stock_quantity"] == 3
    assert filas[1].datos["_variaciones_completas"] == []
