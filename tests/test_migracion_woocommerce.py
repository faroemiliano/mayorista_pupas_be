from app.models.migracion_woocommerce import MigracionWooCommerce
from app.services.migracion_woocommerce_service import importar_muestra


def test_importa_muestra_separada_y_sin_duplicados(monkeypatch, db):
    monkeypatch.setattr("app.services.migracion_woocommerce_service.WooCommerceClient.obtener_producto",lambda self, value:{"id":value,"name":"Producto","_variaciones_completas":[]})
    monkeypatch.setattr("app.services.migracion_woocommerce_service.WooCommerceClient.buscar_cliente_por_email",lambda self, value:{"id":20,"email":value})
    monkeypatch.setattr("app.services.migracion_woocommerce_service.WooCommerceClient.obtener_pedido",lambda self, value:{"id":value,"total":"100"})
    primero=importar_muestra(db,producto_id=10,cliente_email="test@example.com",pedido_id=30)
    segundo=importar_muestra(db,producto_id=10,cliente_email="test@example.com",pedido_id=30)
    assert [fila.tipo for fila,_ in primero]==["producto","cliente","pedido"]
    assert all(creada for _,creada in primero)
    assert not any(creada for _,creada in segundo)
    assert db.query(MigracionWooCommerce).count()==3
