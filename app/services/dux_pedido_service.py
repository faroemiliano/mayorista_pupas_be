import time
from datetime import datetime, timezone

import httpx
from sqlalchemy.orm import Session

from app.core.config import settings
from app.integrations.dux.client import DuxClient
from app.models.pedido import Pedido
from app.repositories.pedido_repository import get_pedido
from app.repositories.reserva_stock_repository import marcar_reservas_enviadas_dux


class DuxPedidoError(ValueError): pass


def _cliente_dux(db: Session, pedido: Pedido, dux: DuxClient) -> int:
    usuario = pedido.usuario
    if usuario and usuario.dux_id_cliente:
        return usuario.dux_id_cliente
    email = pedido.cliente_email or (usuario.email if usuario else None)
    params = {"id_empresa": dux.id_empresa, "limit": 1}
    if usuario and usuario.documento:
        params["nro_doc"] = int(usuario.documento)
    else:
        params["email"] = email
    respuesta = dux.get("v2/clientes", params, reintentos=1)
    datos = respuesta.get("datos") or []
    if not datos and usuario and usuario.documento and email:
        # Algunos clientes existentes no tienen documento cargado en Dux.
        # Antes de crear uno nuevo, hacemos un segundo intento por email.
        time.sleep(5)
        respuesta = dux.get(
            "v2/clientes",
            {"id_empresa": dux.id_empresa, "limit": 1, "email": email},
            reintentos=1,
        )
        datos = respuesta.get("datos") or []
    if datos:
        cliente_id = datos[0]["id_cliente"]
    else:
        time.sleep(5)
        payload = {
            "apellido_razon_social": pedido.cliente_nombre,
            "nombre": pedido.cliente_nombre,
            "categoria_fiscal": "CONSUMIDOR_FINAL",
            "email": email,
            "telefono": pedido.cliente_telefono,
            "domicilio": pedido.direccion,
            "provincia": usuario.provincia if usuario and usuario.provincia else pedido.provincia,
            "localidad": usuario.localidad_partido if usuario and usuario.localidad_partido else pedido.localidad,
            "habilitado": True,
            "id_lista_precio_venta_dflt": settings.DUX_LISTA_PRECIO_MAYORISTA_ID,
        }
        if usuario and (usuario.canal_venta or usuario.tienda_online_url):
            canal = {
                "local_fisico": "Local físico",
                "tienda_online": "Tienda online",
                "ambos": "Local físico y tienda online",
            }.get(usuario.canal_venta, usuario.canal_venta or "")
            payload["observaciones"] = f"Canal de venta web: {canal}"
            if usuario.tienda_online_url:
                payload["observaciones"] += f" | Tienda: {usuario.tienda_online_url}"
        if usuario and usuario.documento:
            payload["tipo_doc"] = "CUIT" if len(usuario.documento) == 11 else "DNI"
            payload["nro_doc"] = int(usuario.documento)
            if len(usuario.documento) == 11:
                payload["cuit_cuil"] = usuario.documento
        creado = dux.post("v2/clientes", payload, {"id_empresa": dux.id_empresa})
        cliente_id = creado["datos"]["id_cliente"]
    if usuario:
        usuario.dux_id_cliente = cliente_id
        db.flush()
    return cliente_id


def enviar_pedido_dux(db: Session, pedido_id: int, id_personal: int) -> Pedido:
    if not settings.DUX_ESCRITURA_HABILITADA:
        raise DuxPedidoError("Modo desarrollo: la escritura en Dux está deshabilitada.")
    if id_personal not in settings.dux_personales_pedidos:
        raise DuxPedidoError("El personal seleccionado no está autorizado para pedidos web.")
    pedido = get_pedido(db, pedido_id)
    if pedido is None: raise DuxPedidoError("Pedido no encontrado.")
    if pedido.estado == "cancelado":
        raise DuxPedidoError("Un pedido cancelado no puede enviarse a Dux.")
    if pedido.dux_id_pedido: return pedido
    pedido.estado_sync_dux = "enviando"; pedido.error_sync_dux = None; db.commit()
    try:
        dux = DuxClient()
        cliente_id = _cliente_dux(db, pedido, dux)
        time.sleep(5)
        cantidades_dux: dict[str, dict] = {}
        for item in pedido.items:
            if item.dux_codigo not in cantidades_dux:
                cantidades_dux[item.dux_codigo] = {"cod_item": item.dux_codigo, "ctd": 0, "precio_uni": float(item.precio_unitario)}
            cantidades_dux[item.dux_codigo]["ctd"] += item.cantidad
        respuesta = dux.post("v2/pedidos", {
            "id_empresa": settings.DUX_ID_EMPRESA,
            "id_sucursal": settings.DUX_ID_SUCURSAL,
            "id_personal": id_personal,
            "id_cliente": cliente_id,
            "id_deposito": settings.DUX_ID_DEPOSITO,
            "fecha": datetime.now().date().isoformat(),
            "referencia": pedido.codigo,
            "observaciones": pedido.observaciones or "Pedido desde tienda web Pupas",
            "lugar_entrega": f"{pedido.direccion}, {pedido.localidad}, {pedido.provincia}",
            "items": list(cantidades_dux.values()),
        })
        datos = respuesta["datos"]
        pedido.dux_id_pedido = datos["id_pedido"]; pedido.dux_nro_pedido = datos.get("nro_pedido")
        pedido.dux_id_personal = id_personal; pedido.estado_sync_dux = "enviado"; pedido.sincronizado_dux_en = datetime.now(timezone.utc)
        marcar_reservas_enviadas_dux(db, pedido.id)
        db.commit(); db.refresh(pedido); return pedido
    except (httpx.HTTPError, KeyError, TypeError, ValueError) as error:
        db.rollback(); pedido = get_pedido(db, pedido_id)
        pedido.estado_sync_dux = "error"; pedido.error_sync_dux = str(error)[:1000]; db.commit()
        raise DuxPedidoError("Dux rechazó el pedido. Revisá el detalle e intentá nuevamente.") from error
