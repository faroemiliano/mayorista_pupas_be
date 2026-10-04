from app.models.migracion_woocommerce import MigracionWooCommerce
from app.models.pedido_historico_wordpress import PedidoHistoricoWordpress
from app.models.producto import Producto
from app.models.usuario import Usuario
from app.models.usuario_wordpress import UsuarioWordpress
from app.services.conversion_pedidos_wordpress_service import convertir_pedidos_wordpress
from app.services.pedido_service import get_pedidos_admin_service


def test_convierte_pedido_historico_sin_generar_pedido_operativo(db):
    usuario = Usuario(email="cliente@test.com", nombre="Ana", apellido="", rol="cliente", estado_registro="aprobado")
    producto = Producto(dux_codigo="WP-10", wordpress_id=10, origen="wordpress", nombre="Pijama", slug="pijama")
    db.add_all([usuario, producto]); db.flush()
    db.add(UsuarioWordpress(wordpress_id=20, usuario_id=usuario.id, email_original=usuario.email))
    db.add(MigracionWooCommerce(tipo="pedido", id_externo="30", checksum="a" * 64, datos={
        "id": 30, "number": "1001", "customer_id": 20, "status": "completed", "currency": "ARS",
        "total": "2500", "discount_total": "0", "shipping_total": "0", "total_tax": "0",
        "date_created": "2025-01-02T10:00:00", "billing": {"email": usuario.email}, "shipping": {},
        "line_items": [{"id": 40, "product_id": 10, "variation_id": 11, "name": "Pijama", "quantity": 2, "subtotal": "2500", "total": "2500", "total_tax": "0", "price": 1250, "meta_data": []}],
    }))
    db.commit()

    resultado = convertir_pedidos_wordpress(db)
    pedido = db.query(PedidoHistoricoWordpress).one()

    assert resultado["creados"] == 1
    assert resultado["items"] == 1
    assert pedido.usuario_id == usuario.id
    assert pedido.items[0].producto_id == producto.id
    assert db.execute(__import__('sqlalchemy').text("select count(*) from pedidos")).scalar_one() == 0

    listado = get_pedidos_admin_service(db, None, 1, 20, origen="wordpress")
    assert listado["items"][0]["cliente_nombre"] == "Ana"
    assert listado["items"][0]["cliente_primer_nombre"] == "Ana"
    assert listado["items"][0]["cliente_apellido"] is None
