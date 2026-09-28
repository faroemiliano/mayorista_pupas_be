import hashlib
import json

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.integrations.woocommerce import WooCommerceClient
from app.models.migracion_woocommerce import MigracionWooCommerce


def _guardar(db: Session, tipo: str, id_externo: str, datos: dict) -> tuple[MigracionWooCommerce, bool]:
    serializado = json.dumps(datos, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    checksum = hashlib.sha256(serializado.encode()).hexdigest()
    fila = db.scalar(select(MigracionWooCommerce).where(
        MigracionWooCommerce.tipo == tipo,
        MigracionWooCommerce.id_externo == str(id_externo),
    ))
    creada = fila is None
    if creada:
        fila = MigracionWooCommerce(tipo=tipo, id_externo=str(id_externo), checksum=checksum, datos=datos)
        db.add(fila)
    elif fila.checksum != checksum:
        fila.checksum = checksum
        fila.datos = datos
    db.commit(); db.refresh(fila)
    return fila, creada


def importar_muestra(db: Session, *, producto_id: int, cliente_email: str, pedido_id: int) -> list[tuple[MigracionWooCommerce, bool]]:
    woo = WooCommerceClient()
    producto = woo.obtener_producto(producto_id)
    cliente = woo.buscar_cliente_por_email(cliente_email)
    if cliente is None:
        raise ValueError("No se encontró el cliente de prueba en WooCommerce.")
    pedido = woo.obtener_pedido(pedido_id)
    return [
        _guardar(db, "producto", str(producto["id"]), producto),
        _guardar(db, "cliente", str(cliente["id"]), cliente),
        _guardar(db, "pedido", str(pedido["id"]), pedido),
    ]
