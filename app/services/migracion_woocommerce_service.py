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


def _guardar_lote(db: Session, tipo: str, elementos: list[dict]) -> tuple[int, int, int]:
    ids = [str(elemento["id"]) for elemento in elementos]
    existentes = {
        fila.id_externo: fila
        for fila in db.scalars(select(MigracionWooCommerce).where(
            MigracionWooCommerce.tipo == tipo,
            MigracionWooCommerce.id_externo.in_(ids),
        )).all()
    }
    creados = actualizados = sin_cambios = 0
    for datos in elementos:
        id_externo = str(datos["id"])
        serializado = json.dumps(datos, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        checksum = hashlib.sha256(serializado.encode()).hexdigest()
        fila = existentes.get(id_externo)
        if fila is None:
            db.add(MigracionWooCommerce(tipo=tipo, id_externo=id_externo, checksum=checksum, datos=datos))
            creados += 1
        elif fila.checksum != checksum:
            fila.checksum = checksum
            fila.datos = datos
            actualizados += 1
        else:
            sin_cambios += 1
    db.commit()
    return creados, actualizados, sin_cambios


def importar_todos_clientes_y_pedidos(db: Session, progreso=None) -> dict:
    woo = WooCommerceClient()
    resultado = {}
    for tipo, recurso in (("cliente", "customers"), ("pedido", "orders")):
        pagina = 1
        paginas = 1
        totales = {"creados": 0, "actualizados": 0, "sin_cambios": 0, "procesados": 0}
        while pagina <= paginas:
            elementos, paginas = woo.obtener_pagina(recurso, pagina)
            creados, actualizados, sin_cambios = _guardar_lote(db, tipo, elementos)
            totales["creados"] += creados
            totales["actualizados"] += actualizados
            totales["sin_cambios"] += sin_cambios
            totales["procesados"] += len(elementos)
            if progreso:
                progreso(tipo, pagina, paginas, totales.copy())
            pagina += 1
        resultado[tipo] = totales
    return resultado


def importar_todos_productos(db: Session, progreso=None) -> dict:
    woo = WooCommerceClient()
    pagina = 1
    paginas = 1
    total = {"creados": 0, "actualizados": 0, "sin_cambios": 0, "procesados": 0}
    while pagina <= paginas:
        productos, paginas = woo.obtener_pagina("products", pagina)
        for producto in productos:
            producto["_variaciones_completas"] = (
                woo.obtener_variaciones(int(producto["id"]))
                if producto.get("type") == "variable"
                else []
            )
            creados, actualizados, sin_cambios = _guardar_lote(db, "producto", [producto])
            total["creados"] += creados
            total["actualizados"] += actualizados
            total["sin_cambios"] += sin_cambios
            total["procesados"] += 1
            if progreso:
                progreso(pagina, paginas, producto, total.copy())
        pagina += 1
    return total


def importar_todas_categorias(db: Session) -> dict:
    woo = WooCommerceClient()
    pagina = 1
    paginas = 1
    total = {"creados": 0, "actualizados": 0, "sin_cambios": 0, "procesados": 0}
    while pagina <= paginas:
        categorias, paginas = woo.obtener_pagina("products/categories", pagina)
        creados, actualizados, sin_cambios = _guardar_lote(db, "categoria", categorias)
        total["creados"] += creados
        total["actualizados"] += actualizados
        total["sin_cambios"] += sin_cambios
        total["procesados"] += len(categorias)
        pagina += 1
    return total
