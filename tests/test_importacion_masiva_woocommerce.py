from app.models.migracion_woocommerce import MigracionWooCommerce
from app.services.migracion_woocommerce_service import importar_todos_clientes_y_pedidos


def test_importacion_masiva_es_paginada_e_idempotente(monkeypatch, db):
    paginas = {
        "customers": {1: ([{"id": 1, "email": "uno@test.com"}], 2), 2: ([{"id": 2, "email": "dos@test.com"}], 2)},
        "orders": {1: ([{"id": 10, "total": "100"}], 1)},
    }
    monkeypatch.setattr(
        "app.services.migracion_woocommerce_service.WooCommerceClient.obtener_pagina",
        lambda self, recurso, pagina: paginas[recurso][pagina],
    )

    primero = importar_todos_clientes_y_pedidos(db)
    segundo = importar_todos_clientes_y_pedidos(db)

    assert primero["cliente"]["creados"] == 2
    assert primero["pedido"]["creados"] == 1
    assert segundo["cliente"]["sin_cambios"] == 2
    assert segundo["pedido"]["sin_cambios"] == 1
    assert db.query(MigracionWooCommerce).count() == 3
