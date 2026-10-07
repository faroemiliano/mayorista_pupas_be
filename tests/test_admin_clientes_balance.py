from datetime import datetime, timezone
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.pedido import Pedido
from app.models.pedido_historico_wordpress import PedidoHistoricoWordpress, PedidoItemHistoricoWordpress
from app.models.usuario import Usuario


def _pedido(codigo: str, usuario_id: int, total: str, unidades: int, creado_en: datetime, estado: str = "confirmado") -> Pedido:
    return Pedido(
        usuario_id=usuario_id, codigo=codigo, estado=estado,
        cliente_nombre="Cliente", cliente_telefono="11111111", provincia="Santa Fe", localidad="Rosario", direccion="Sin domicilio",
        cantidad_productos_diferentes=1, cantidad_unidades=unidades, aplica_precio_24_productos=False,
        subtotal_sin_descuento=Decimal(total), descuento_aplicado=Decimal("0"), total=Decimal(total), creado_en=creado_en,
    )


def test_balance_compras_cliente_incluye_tienda_wordpress_y_filtros_de_fecha(client: TestClient, db: Session):
    usuario = Usuario(email="cliente@test.local", nombre="Cliente", apellido="Prueba", rol="cliente", estado_registro="aprobado")
    db.add(usuario)
    db.flush()
    db.add_all([
        _pedido("PUP-CLIENTE-1", usuario.id, "150", 3, datetime(2026, 10, 2, 12, tzinfo=timezone.utc)),
        _pedido("PUP-CLIENTE-CANCELADO", usuario.id, "999", 9, datetime(2026, 10, 3, 12, tzinfo=timezone.utc), "cancelado"),
    ])
    historico = PedidoHistoricoWordpress(
        wordpress_id=9001, numero="9001", usuario_id=usuario.id, wordpress_customer_id=101, estado="completed", total=Decimal("300"),
        creado_en_wordpress=datetime(2026, 9, 15, 12, tzinfo=timezone.utc), facturacion={}, envio={},
    )
    db.add(historico)
    db.flush()
    db.add(PedidoItemHistoricoWordpress(pedido_id=historico.id, wordpress_id=1, wordpress_product_id=1, nombre="Producto", cantidad=4, subtotal=Decimal("300"), total=Decimal("300")))
    db.commit()

    response = client.get(f"/api/admin/usuarios/{usuario.id}/balance-compras")

    assert response.status_code == 200, response.text
    assert response.json()["acumulado"] == {"pedidos": 2, "unidades": 7, "importe": 450.0}

    filtrado = client.get(f"/api/admin/usuarios/{usuario.id}/balance-compras", params={"fecha_desde": "2026-09-01", "fecha_hasta": "2026-09-30"})
    assert filtrado.status_code == 200, filtrado.text
    assert filtrado.json()["periodo"] == {"pedidos": 1, "unidades": 4, "importe": 300.0}
