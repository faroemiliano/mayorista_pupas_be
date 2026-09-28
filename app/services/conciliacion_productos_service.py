from collections import defaultdict
from datetime import datetime, timezone
from difflib import SequenceMatcher

from slugify import slugify
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.integrations.dux.client import DuxClient
from app.models.migracion_woocommerce import MigracionWooCommerce
from app.models.producto import Producto
from app.services.dux_sync_service import _obtener_pagina_items_dux
from app.services.migracion_woocommerce_service import _guardar


def _normalizar(valor: str | None) -> str:
    return slugify(valor or "", separator=" ").strip()


def _sku_wordpress(producto: dict) -> set[str]:
    codigos = {str(producto.get("sku") or "").strip().lower()}
    codigos.update(
        str(variacion.get("sku") or "").strip().lower()
        for variacion in producto.get("_variaciones_completas") or []
    )
    codigos.discard("")
    return codigos


def _precios_wordpress(producto: dict) -> list[float]:
    valores = [producto.get("price")]
    valores.extend(item.get("price") for item in producto.get("_variaciones_completas") or [])
    precios = set()
    for valor in valores:
        try:
            precio = float(valor)
        except (TypeError, ValueError):
            continue
        if precio > 0:
            precios.add(precio)
    return sorted(precios)


def _precios_dux(producto: dict) -> list[dict]:
    precios = []
    for item in producto.get("precios") or []:
        try:
            precio = float(item.get("precio") or 0)
        except (TypeError, ValueError):
            continue
        if precio > 0:
            precios.append({"id": item.get("id"), "nombre": item.get("nombre"), "precio": precio})
    return precios


def _detalle_wordpress(producto: dict) -> dict:
    imagenes = producto.get("images") or []
    talles = []
    for variacion in producto.get("_variaciones_completas") or []:
        for atributo in variacion.get("attributes") or []:
            if any(token in str(atributo.get("name") or "").lower() for token in ("talle", "talla", "size")):
                valor = str(atributo.get("option") or "").strip()
                if valor and valor not in talles:
                    talles.append(valor)
    return {
        "wordpress_imagen": imagenes[0].get("src") if imagenes else None,
        "wordpress_precios": _precios_wordpress(producto),
        "wordpress_skus": sorted(_sku_wordpress(producto)),
        "wordpress_talles": talles,
    }


def _detalle_dux(producto: dict) -> dict:
    talles = sorted({str(item.get("talle") or "").strip() for item in producto.get("stock") or [] if item.get("talle")})
    return {
        "dux_imagen": producto.get("imagen_url") or None,
        "dux_precios": _precios_dux(producto),
        "dux_talles": talles,
    }


def conciliar_productos(productos_wordpress: list[dict], productos_dux: list[dict]) -> dict:
    dux_por_codigo: dict[str, list[dict]] = defaultdict(list)
    dux_por_nombre: dict[str, list[dict]] = defaultdict(list)
    for producto in productos_dux:
        codigo = str(producto.get("cod_item") or "").strip().lower()
        if codigo:
            dux_por_codigo[codigo].append(producto)
        dux_por_nombre[_normalizar(producto.get("item"))].append(producto)

    coincidencias = []
    dudosos = []
    solo_wordpress = []
    dux_usados: set[str] = set()
    nombres_dux = list(dux_por_nombre)

    for wp in productos_wordpress:
        candidatos_codigo = {
            str(item.get("cod_item")): item
            for sku in _sku_wordpress(wp)
            for item in dux_por_codigo.get(sku, [])
        }
        nombre_normalizado = _normalizar(wp.get("name"))
        candidatos_nombre = dux_por_nombre.get(nombre_normalizado, [])
        candidato = None
        criterio = None
        if len(candidatos_codigo) == 1:
            candidato = next(iter(candidatos_codigo.values()))
            criterio = "codigo"
        elif not candidatos_codigo and len(candidatos_nombre) == 1:
            candidato = candidatos_nombre[0]
            criterio = "nombre_exacto"

        if candidato:
            codigo_dux = str(candidato.get("cod_item") or "")
            if codigo_dux in dux_usados:
                dudosos.append({
                    "wordpress_id": str(wp.get("id")), "wordpress_nombre": wp.get("name"),
                    "dux_codigo_sugerido": codigo_dux, "dux_nombre_sugerido": candidato.get("item"),
                    "similitud": 1.0, "motivo": "El producto Dux ya coincide con otro producto de WordPress.",
                    **_detalle_wordpress(wp), **_detalle_dux(candidato),
                })
                continue
            dux_usados.add(codigo_dux)
            coincidencias.append({
                "wordpress_id": str(wp.get("id")), "wordpress_nombre": wp.get("name"),
                "dux_codigo": codigo_dux, "dux_nombre": candidato.get("item"), "criterio": criterio,
                **_detalle_wordpress(wp), **_detalle_dux(candidato),
            })
            continue

        mejor_nombre = ""
        mejor_puntaje = 0.0
        for nombre_dux in nombres_dux:
            puntaje = SequenceMatcher(None, nombre_normalizado, nombre_dux).ratio()
            if puntaje > mejor_puntaje:
                mejor_nombre, mejor_puntaje = nombre_dux, puntaje
        registro_wp = {"wordpress_id": str(wp.get("id")), "wordpress_nombre": wp.get("name")}
        if mejor_puntaje >= 0.82 and dux_por_nombre.get(mejor_nombre):
            sugerido = dux_por_nombre[mejor_nombre][0]
            dudosos.append({
                **registro_wp,
                "dux_codigo_sugerido": str(sugerido.get("cod_item") or ""),
                "dux_nombre_sugerido": sugerido.get("item"),
                "similitud": round(mejor_puntaje, 3),
                **_detalle_wordpress(wp), **_detalle_dux(sugerido),
            })
        else:
            solo_wordpress.append(registro_wp)

    solo_dux = [
        {"dux_codigo": str(item.get("cod_item") or ""), "dux_nombre": item.get("item")}
        for item in productos_dux
        if str(item.get("cod_item") or "") not in dux_usados
    ]
    return {
        "totales": {
            "wordpress": len(productos_wordpress), "dux": len(productos_dux),
            "coincidencias": len(coincidencias), "dudosos": len(dudosos),
            "solo_wordpress": len(solo_wordpress), "solo_dux": len(solo_dux),
        },
        "coincidencias": coincidencias,
        "dudosos": dudosos,
        "solo_wordpress": solo_wordpress,
        "solo_dux": solo_dux,
    }


def generar_conciliacion(db: Session, progreso=None) -> dict:
    productos_wordpress = [
        fila.datos for fila in db.scalars(
            select(MigracionWooCommerce).where(MigracionWooCommerce.tipo == "producto")
        ).all()
    ]
    dux = DuxClient()
    productos_dux = []
    offset = 0
    limit = 50
    omitidos: list[int] = []
    total_informado = 0
    while True:
        respuesta, omitidos_pagina = _obtener_pagina_items_dux(dux, offset, limit)
        omitidos.extend(omitidos_pagina)
        productos_dux.extend(respuesta.get("datos") or [])
        total_informado = int((respuesta.get("paginacion") or {}).get("total") or 0)
        if progreso:
            progreso(len(productos_dux), total_informado)
        if not (respuesta.get("paginacion") or {}).get("hay_mas"):
            break
        offset += limit
    resultado = conciliar_productos(productos_wordpress, productos_dux)
    resultado["totales"]["dux_informados"] = total_informado
    resultado["totales"]["dux_omitidos_por_error"] = len(omitidos)
    resultado["offsets_dux_omitidos"] = omitidos
    _guardar(db, "conciliacion", "productos-wordpress-dux", resultado)
    return resultado


def aplicar_coincidencias_seguras(db: Session) -> dict:
    fila = db.scalar(select(MigracionWooCommerce).where(
        MigracionWooCommerce.tipo == "conciliacion",
        MigracionWooCommerce.id_externo == "productos-wordpress-dux",
    ))
    if fila is None:
        raise ValueError("Primero debe generarse el informe de conciliación.")

    resultado = {"vinculados": 0, "ya_vinculados": 0, "omitidos": 0, "conflictos": []}
    for coincidencia in fila.datos.get("coincidencias") or []:
        wordpress_id = int(coincidencia["wordpress_id"])
        codigo_dux = str(coincidencia["dux_codigo"]).strip()
        producto = db.scalar(select(Producto).where(Producto.wordpress_id == wordpress_id))
        if producto is None or not codigo_dux:
            resultado["omitidos"] += 1
            continue
        conflicto = db.scalar(select(Producto).where(
            Producto.dux_codigo == codigo_dux,
            Producto.id != producto.id,
        ))
        if conflicto is not None:
            resultado["conflictos"].append({
                "wordpress_id": wordpress_id, "dux_codigo": codigo_dux,
                "producto_local_id": conflicto.id,
            })
            continue
        if producto.conciliacion_estado == "vinculado" and producto.dux_codigo == codigo_dux:
            resultado["ya_vinculados"] += 1
            continue
        producto.dux_codigo = codigo_dux
        producto.origen = "wordpress_dux"
        producto.conciliacion_estado = "vinculado"
        producto.conciliacion_criterio = coincidencia.get("criterio")
        producto.conciliado_en = datetime.now(timezone.utc)
        resultado["vinculados"] += 1

    if resultado["conflictos"]:
        db.rollback()
        raise ValueError(
            f"Se detectaron {len(resultado['conflictos'])} códigos Dux ya asignados; no se aplicó ningún cambio."
        )
    db.commit()
    resultado["total_vinculados"] = db.scalar(
        select(func.count(Producto.id)).where(Producto.conciliacion_estado == "vinculado")
    ) or 0
    return resultado


def vincular_coincidencia_manual(db: Session, wordpress_id: int, dux_codigo: str) -> Producto:
    fila = db.scalar(select(MigracionWooCommerce).where(
        MigracionWooCommerce.tipo == "conciliacion",
        MigracionWooCommerce.id_externo == "productos-wordpress-dux",
    ))
    if fila is None:
        raise ValueError("No existe un informe de conciliación.")
    sugerencia = next((item for item in fila.datos.get("dudosos") or []
                       if int(item["wordpress_id"]) == wordpress_id), None)
    if sugerencia is None or str(sugerencia.get("dux_codigo_sugerido") or "").strip() != dux_codigo.strip():
        raise ValueError("La relación propuesta no pertenece al informe pendiente.")
    producto = db.scalar(select(Producto).where(Producto.wordpress_id == wordpress_id))
    if producto is None:
        raise ValueError("El producto de WordPress no existe en el catálogo local.")
    conflicto = db.scalar(select(Producto).where(
        Producto.dux_codigo == dux_codigo.strip(), Producto.id != producto.id,
    ))
    if conflicto is not None:
        raise ValueError("Ese producto de Dux ya está relacionado con otro producto de WordPress.")
    producto.dux_codigo = dux_codigo.strip()
    producto.origen = "wordpress_dux"
    producto.conciliacion_estado = "vinculado"
    producto.conciliacion_criterio = "manual"
    producto.conciliado_en = datetime.now(timezone.utc)
    db.commit()
    db.refresh(producto)
    return producto
