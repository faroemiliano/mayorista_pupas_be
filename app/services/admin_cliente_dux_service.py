import time
from datetime import datetime, timezone
from collections.abc import Callable

from sqlalchemy import func, or_, select, update
from sqlalchemy.orm import Session

from app.integrations.dux.client import DuxClient
from app.models.cliente_dux import ClienteDux
from app.models.usuario import Usuario


def _texto(value) -> str | None:
    if value is None:
        return None
    result = str(value).strip()
    return result or None


def _fecha(value) -> datetime | None:
    if isinstance(value, datetime):
        return value
    text = _texto(value)
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None


def sincronizar_clientes_dux(
    db: Session,
    progreso: Callable[[int, int, int], None] | None = None,
) -> dict:
    dux = DuxClient()
    limite, offset = 50, 0
    procesados = creados = actualizados = 0
    instante = datetime.now(timezone.utc)
    firmas: set[tuple[int, ...]] = set()
    db.execute(update(ClienteDux).values(presente_en_dux=False))

    while True:
        respuesta = dux.get("v2/clientes", {
            "id_empresa": dux.id_empresa, "offset": offset, "limit": limite,
        }, reintentos=2)
        datos = respuesta.get("datos") or []
        if not datos:
            break
        firma = tuple(int(item["id_cliente"]) for item in datos if item.get("id_cliente"))
        if not firma or firma in firmas:
            raise RuntimeError("Dux repitió una página de clientes; se canceló la sincronización.")
        firmas.add(firma)
        existentes = {
            c.dux_id_cliente: c
            for c in db.scalars(select(ClienteDux).where(ClienteDux.dux_id_cliente.in_(firma))).all()
        }
        for data in datos:
            dux_id = int(data["id_cliente"])
            cliente = existentes.get(dux_id)
            if cliente is None:
                cliente = ClienteDux(dux_id_cliente=dux_id, nombre="")
                db.add(cliente)
                creados += 1
            else:
                actualizados += 1
            cliente.codigo = _texto(data.get("codigo"))
            cliente.nombre = _texto(data.get("full_name")) or " ".join(filter(None, [
                _texto(data.get("nombre")), _texto(data.get("apellido_razon_social")),
            ])) or f"Cliente Dux {dux_id}"
            cliente.email = _texto(data.get("email"))
            cliente.telefono = _texto(data.get("telefono") or data.get("cel"))
            cliente.tipo_doc = _texto(data.get("tipo_doc"))
            cliente.nro_doc = _texto(data.get("nro_doc"))
            cliente.cuit_cuil = _texto(data.get("cuit_cuil"))
            cliente.domicilio = _texto(data.get("domicilio"))
            cliente.localidad = _texto(data.get("localidad"))
            cliente.provincia = _texto(data.get("provincia"))
            cliente.habilitado = bool(data.get("habilitado", True))
            cliente.presente_en_dux = True
            cliente.fecha_creacion_dux = _fecha(data.get("fecha_creacion"))
            cliente.sincronizado_en = instante
            procesados += 1
        db.flush()
        if progreso:
            progreso(procesados, creados, actualizados)
        if len(datos) < limite:
            break
        offset += limite
        time.sleep(5)

    if procesados == 0:
        raise RuntimeError("Dux devolvió una lista vacía; no se modificaron los clientes locales.")
    db.commit()
    total = db.scalar(select(func.count()).select_from(ClienteDux).where(ClienteDux.presente_en_dux.is_(True))) or 0
    return {"procesados": procesados, "creados": creados, "actualizados": actualizados,
            "total_local": total, "sincronizado_en": instante}


def listar_clientes_dux(db: Session, pagina: int, limite: int, buscar: str | None = None) -> dict:
    filtros = [ClienteDux.presente_en_dux.is_(True)]
    if buscar and buscar.strip():
        term = f"%{buscar.strip()}%"
        filtros.append(or_(ClienteDux.nombre.ilike(term), ClienteDux.email.ilike(term),
                           ClienteDux.telefono.ilike(term), ClienteDux.nro_doc.ilike(term),
                           ClienteDux.cuit_cuil.ilike(term), ClienteDux.codigo.ilike(term)))
    total = db.scalar(select(func.count()).select_from(ClienteDux).where(*filtros)) or 0
    clientes = list(db.scalars(select(ClienteDux).where(*filtros).order_by(ClienteDux.nombre.asc())
                               .offset((pagina - 1) * limite).limit(limite)).all())
    documentos = {c.nro_doc or c.cuit_cuil for c in clientes if c.nro_doc or c.cuit_cuil}
    emails = {c.email.lower() for c in clientes if c.email}
    ids = {c.dux_id_cliente for c in clientes}
    condiciones = [Usuario.dux_id_cliente.in_(ids)]
    if documentos:
        condiciones.append(Usuario.documento.in_(documentos))
    if emails:
        condiciones.append(Usuario.email.in_(emails))
    usuarios = list(db.scalars(select(Usuario).where(or_(*condiciones))).all())
    por_dux = {u.dux_id_cliente: u for u in usuarios if u.dux_id_cliente}
    por_doc = {u.documento: u for u in usuarios if u.documento}
    por_email = {u.email.lower(): u for u in usuarios}
    items = []
    for cliente in clientes:
        documento = cliente.nro_doc or cliente.cuit_cuil
        usuario = por_dux.get(cliente.dux_id_cliente)
        criterio = "id_dux" if usuario else None
        if usuario is None and documento:
            usuario = por_doc.get(documento)
            criterio = "documento" if usuario else None
        if usuario is None and cliente.email:
            usuario = por_email.get(cliente.email.lower())
            criterio = "email" if usuario else None
        items.append({
            "id_cliente": cliente.dux_id_cliente, "codigo": cliente.codigo, "nombre": cliente.nombre,
            "email": cliente.email or (usuario.email if usuario else None), "telefono": cliente.telefono,
            "tipo_doc": cliente.tipo_doc, "nro_doc": cliente.nro_doc, "cuit_cuil": cliente.cuit_cuil,
            "localidad": cliente.localidad, "provincia": cliente.provincia, "habilitado": cliente.habilitado,
            "fecha_creacion": cliente.fecha_creacion_dux, "usuario_id": usuario.id if usuario else None,
            "usuario_estado": usuario.estado_registro if usuario else None, "criterio_vinculacion": criterio,
        })
    ultima = db.scalar(select(func.max(ClienteDux.sincronizado_en)))
    return {"items": items, "total": total, "pagina": pagina, "limite": limite,
            "hay_mas": pagina * limite < total, "ultima_sincronizacion": ultima}


def contar_clientes_dux(db: Session) -> dict:
    total = db.scalar(select(func.count()).select_from(ClienteDux).where(ClienteDux.presente_en_dux.is_(True))) or 0
    return {"total": total, "cache_segundos": 0}
