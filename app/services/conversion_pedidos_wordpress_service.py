from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation

from sqlalchemy import delete, insert, select
from sqlalchemy.orm import Session

from app.models.migracion_woocommerce import MigracionWooCommerce
from app.models.pedido_historico_wordpress import PedidoHistoricoWordpress, PedidoItemHistoricoWordpress
from app.models.producto import Producto
from app.models.usuario_wordpress import UsuarioWordpress


def _decimal(valor) -> Decimal:
    try:
        return Decimal(str(valor or 0))
    except (InvalidOperation, ValueError):
        return Decimal("0")


def _fecha(valor: str | None, requerida: bool = False) -> datetime | None:
    if valor:
        try:
            return datetime.fromisoformat(valor.replace("Z", "+00:00"))
        except ValueError:
            pass
    return datetime.now(timezone.utc) if requerida else None


def convertir_pedidos_wordpress(db: Session, progreso=None) -> dict:
    usuarios = {enlace.wordpress_id: enlace.usuario_id for enlace in db.scalars(select(UsuarioWordpress)).all()}
    productos = {producto.wordpress_id: producto.id for producto in db.scalars(select(Producto).where(Producto.wordpress_id.is_not(None))).all()}
    pedidos_existentes = {pedido.wordpress_id: pedido for pedido in db.scalars(select(PedidoHistoricoWordpress)).all()}
    resultado = {
        "procesados": 0, "creados": 0, "actualizados": 0, "items": 0,
        "pedidos_sin_cuenta": 0, "items_sin_producto": 0,
    }
    ultimo_id = 0
    while True:
        # Procesamos lotes para que Render Free no tenga que cargar los 15k
        # pedidos y sus líneas completas en memoria de una sola vez.
        filas = list(db.scalars(
            select(MigracionWooCommerce)
            .where(MigracionWooCommerce.tipo == "pedido", MigracionWooCommerce.id > ultimo_id)
            .order_by(MigracionWooCommerce.id.asc())
            .limit(250)
        ).all())
        if not filas:
            break
        for fila in filas:
            ultimo_id = fila.id
            datos = fila.datos
            wordpress_id = int(datos["id"])
            pedido = pedidos_existentes.get(wordpress_id)
            creado = pedido is None
            if creado:
                pedido = PedidoHistoricoWordpress(
                    wordpress_id=wordpress_id,
                    numero=str(datos.get("number") or wordpress_id),
                    wordpress_customer_id=int(datos.get("customer_id") or 0),
                    estado=str(datos.get("status") or "desconocido"),
                    creado_en_wordpress=_fecha(datos.get("date_created") or datos.get("date_created_gmt"), requerida=True),
                )
                db.add(pedido); db.flush()
                pedidos_existentes[wordpress_id] = pedido
            customer_id = int(datos.get("customer_id") or 0)
            pedido.numero = str(datos.get("number") or wordpress_id)
            pedido.wordpress_customer_id = customer_id
            pedido.usuario_id = usuarios.get(customer_id)
            pedido.estado = str(datos.get("status") or "desconocido")
            pedido.moneda = str(datos.get("currency") or "ARS")
            pedido.total = _decimal(datos.get("total"))
            pedido.descuento_total = _decimal(datos.get("discount_total"))
            pedido.envio_total = _decimal(datos.get("shipping_total"))
            pedido.impuesto_total = _decimal(datos.get("total_tax"))
            pedido.metodo_pago = datos.get("payment_method") or None
            pedido.titulo_pago = datos.get("payment_method_title") or None
            pedido.facturacion = datos.get("billing") or {}
            pedido.envio = datos.get("shipping") or {}
            pedido.creado_en_wordpress = _fecha(datos.get("date_created") or datos.get("date_created_gmt"), requerida=True)
            pedido.pagado_en_wordpress = _fecha(datos.get("date_paid") or datos.get("date_paid_gmt"))
            pedido.completado_en_wordpress = _fecha(datos.get("date_completed") or datos.get("date_completed_gmt"))
            if pedido.usuario_id is None:
                resultado["pedidos_sin_cuenta"] += 1

            db.execute(delete(PedidoItemHistoricoWordpress).where(PedidoItemHistoricoWordpress.pedido_id == pedido.id))
            items_para_insertar = []
            for item in datos.get("line_items") or []:
                wordpress_product_id = int(item.get("product_id") or 0)
                producto_id = productos.get(wordpress_product_id)
                if producto_id is None:
                    resultado["items_sin_producto"] += 1
                items_para_insertar.append({
                    "pedido_id": pedido.id,
                    "wordpress_id": int(item.get("id") or 0),
                    "wordpress_product_id": wordpress_product_id,
                    "wordpress_variation_id": int(item.get("variation_id") or 0),
                    "producto_id": producto_id,
                    "nombre": str(item.get("name") or "Producto histórico"),
                    "sku": (item.get("sku") or "").strip() or None,
                    "cantidad": int(item.get("quantity") or 0),
                    "subtotal": _decimal(item.get("subtotal")),
                    "total": _decimal(item.get("total")),
                    "impuesto_total": _decimal(item.get("total_tax")),
                    "precio_unitario": _decimal(item.get("price")),
                    "metadatos": item.get("meta_data") or [],
                })
                resultado["items"] += 1
            if items_para_insertar:
                db.execute(insert(PedidoItemHistoricoWordpress), items_para_insertar)
            resultado["creados" if creado else "actualizados"] += 1
            resultado["procesados"] += 1
        db.commit()
        if progreso:
            progreso(resultado.copy())
    db.commit()
    return resultado
