"""Auditoría de solo lectura para las imágenes de catálogo.

No modifica URLs, objetos R2 ni registros: inspecciona las referencias actuales
y sólo descarga los archivos que deben analizarse por peso/dimensiones.
"""

from __future__ import annotations

from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from io import BytesIO
from urllib.parse import unquote, urlsplit

import httpx
from PIL import Image, UnidentifiedImageError
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.core.config import settings
from app.models.imagen_producto import ImagenProducto
from app.models.migracion_woocommerce import MigracionWooCommerce
from app.models.producto import Producto
from app.database.session import SessionLocal
from app.services.almacenamiento_imagenes_r2_service import (
    _cliente_r2,
    r2_imagenes_configurado,
    subir_imagen_producto_a_r2,
)
from app.services.migracion_woocommerce_service import _guardar
from app.services.procesamiento_imagenes_service import ImagenInvalidaError, procesar_imagen_catalogo


UMBRAL_PESADO = 1 * 1024 * 1024
UMBRALES = (1, 2, 5, 8)
TIPO_ESTADO = "diagnostico_imagenes_r2"
ID_ESTADO = "catalogo"
TIPO_OPTIMIZACION = "optimizacion_imagenes_r2"
ID_OPTIMIZACION = "catalogo"


def _estado(db: Session, **cambios) -> dict:
    fila = db.scalar(select(MigracionWooCommerce).where(
        MigracionWooCommerce.tipo == TIPO_ESTADO,
        MigracionWooCommerce.id_externo == ID_ESTADO,
    ))
    datos = dict(fila.datos) if fila else {}
    datos.update(cambios)
    _guardar(db, TIPO_ESTADO, ID_ESTADO, datos)
    return datos


def obtener_estado_diagnostico_imagenes_r2(db: Session) -> dict:
    """Estado persistente del último análisis, sin tocar el catálogo."""
    fila = db.scalar(select(MigracionWooCommerce).where(
        MigracionWooCommerce.tipo == TIPO_ESTADO,
        MigracionWooCommerce.id_externo == ID_ESTADO,
    ))
    if fila is None:
        return {"estado": "pendiente", "resultado": None, "error": None}
    return dict(fila.datos)


def preparar_diagnostico_imagenes_r2(db: Session) -> dict:
    actual = obtener_estado_diagnostico_imagenes_r2(db)
    if actual.get("estado") == "en_progreso":
        raise ValueError("El diagnóstico de imágenes ya está en progreso.")
    return _estado(
        db,
        estado="en_progreso",
        resultado=None,
        error=None,
        iniciada_en=datetime.now(timezone.utc).isoformat(),
        finalizada_en=None,
    )


def ejecutar_diagnostico_imagenes_r2_background() -> None:
    """Ejecuta el análisis fuera de la petición HTTP y persiste sólo su informe."""
    with SessionLocal() as db:
        try:
            resultado = obtener_diagnostico_avanzado_imagenes_r2(db)
            _estado(
                db,
                estado="completado",
                resultado=resultado,
                error=None,
                finalizada_en=datetime.now(timezone.utc).isoformat(),
            )
        except Exception as error:
            _estado(
                db,
                estado="error",
                error=str(error)[:1000],
                finalizada_en=datetime.now(timezone.utc).isoformat(),
            )


def _estado_optimizacion(db: Session, **cambios) -> dict:
    fila = db.scalar(select(MigracionWooCommerce).where(
        MigracionWooCommerce.tipo == TIPO_OPTIMIZACION,
        MigracionWooCommerce.id_externo == ID_OPTIMIZACION,
    ))
    datos = dict(fila.datos) if fila else {}
    datos.update(cambios)
    _guardar(db, TIPO_OPTIMIZACION, ID_OPTIMIZACION, datos)
    return datos


def obtener_estado_optimizacion_imagenes_r2(db: Session) -> dict:
    fila = db.scalar(select(MigracionWooCommerce).where(
        MigracionWooCommerce.tipo == TIPO_OPTIMIZACION,
        MigracionWooCommerce.id_externo == ID_OPTIMIZACION,
    ))
    if fila is None:
        return {"estado": "pendiente", "progreso": None, "resultado": None, "error": None}
    return dict(fila.datos)


def _objetivos_optimizacion(db: Session) -> list[dict]:
    diagnostico = obtener_estado_diagnostico_imagenes_r2(db)
    if diagnostico.get("estado") != "completado" or not diagnostico.get("resultado"):
        raise ValueError("Primero ejecutá y esperá a que termine el análisis del catálogo.")
    return [
        detalle for detalle in diagnostico["resultado"].get("imagenes_pesadas", [])
        if int(detalle.get("peso_bytes") or 0) > UMBRAL_PESADO
    ]


def preparar_optimizacion_imagenes_r2(db: Session) -> dict:
    if not r2_imagenes_configurado():
        raise ValueError("R2 no está configurado en el backend.")
    actual = obtener_estado_optimizacion_imagenes_r2(db)
    if actual.get("estado") == "en_progreso":
        raise ValueError("La optimización de imágenes ya está en progreso.")
    objetivos = _objetivos_optimizacion(db)
    if not objetivos:
        raise ValueError("El análisis no encontró imágenes de más de 1 MB para optimizar.")
    return _estado_optimizacion(
        db,
        estado="en_progreso",
        progreso={"total": len(objetivos), "procesadas": 0, "optimizadas": 0, "sin_ahorro": 0, "fallidas": 0},
        resultado=None,
        error=None,
        iniciada_en=datetime.now(timezone.utc).isoformat(),
        finalizada_en=None,
    )


def _contenido_para_optimizar(imagen: ImagenProducto | None, url: str) -> tuple[bytes, str | None]:
    if imagen is not None and imagen.contenido is not None:
        return imagen.contenido, imagen.media_type
    return _leer_remota(url)


def optimizar_imagenes_pesadas_r2(db: Session) -> dict:
    """Optimiza sólo las fotos pesadas halladas por el último diagnóstico.

    Cada foto se sube primero con una URL inmutable y se actualiza la referencia
    recién después de verificarla. Los objetos originales no se eliminan.
    """
    objetivos = _objetivos_optimizacion(db)
    procesadas = optimizadas = sin_ahorro = fallidas = 0
    ahorro_total = 0
    errores: list[dict] = []
    for objetivo in objetivos:
        imagen_id = objetivo.get("imagen_id")
        producto_id = int(objetivo["producto_id"])
        url_original = str(objetivo["url"])
        imagen = db.get(ImagenProducto, imagen_id) if imagen_id is not None else None
        producto = db.get(Producto, producto_id)
        try:
            if producto is None:
                raise ValueError("El producto ya no existe.")
            if imagen is not None:
                if imagen.url != url_original:
                    raise ValueError("La foto cambió desde el análisis; ejecutá uno nuevo antes de optimizarla.")
                url_actual = imagen.url
            else:
                if producto.imagen_url != url_original:
                    raise ValueError("La portada cambió desde el análisis; ejecutá uno nuevo antes de optimizarla.")
                url_actual = producto.imagen_url
            if not url_actual:
                raise ValueError("La foto no tiene una URL válida.")

            contenido, media_type = _contenido_para_optimizar(imagen, url_actual)
            media_type = media_type.split(";", 1)[0] if media_type else None
            procesada = procesar_imagen_catalogo(contenido, media_type_declarado=media_type)
            if procesada.peso >= len(contenido):
                sin_ahorro += 1
            else:
                nueva_url = subir_imagen_producto_a_r2(
                    contenido=procesada.contenido,
                    producto_id=producto.id,
                    media_type=procesada.media_type,
                )
                if imagen is not None:
                    imagen.url = nueva_url
                    if imagen.principal or producto.imagen_url == url_actual:
                        producto.imagen_url = nueva_url
                else:
                    producto.imagen_url = nueva_url
                db.commit()
                optimizadas += 1
                ahorro_total += len(contenido) - procesada.peso
        except Exception as error:
            db.rollback()
            fallidas += 1
            if len(errores) < 50:
                errores.append({
                    "imagen_id": imagen_id,
                    "producto_id": producto_id,
                    "error": str(error)[:300],
                })
        procesadas += 1
        _estado_optimizacion(
            db,
            estado="en_progreso",
            progreso={"total": len(objetivos), "procesadas": procesadas, "optimizadas": optimizadas, "sin_ahorro": sin_ahorro, "fallidas": fallidas},
            errores=errores,
        )
    resultado = {
        "procesadas": procesadas,
        "optimizadas": optimizadas,
        "sin_ahorro": sin_ahorro,
        "fallidas": fallidas,
        "ahorro_bytes": ahorro_total,
        "ahorro_mb": round(ahorro_total / 1024 / 1024, 2),
        "originales_conservados": True,
    }
    _estado_optimizacion(
        db,
        estado="completada",
        progreso=None,
        resultado=resultado,
        error=None,
        errores=errores,
        finalizada_en=datetime.now(timezone.utc).isoformat(),
    )
    return resultado


def ejecutar_optimizacion_imagenes_r2_background() -> None:
    with SessionLocal() as db:
        try:
            optimizar_imagenes_pesadas_r2(db)
        except Exception as error:
            _estado_optimizacion(
                db,
                estado="error",
                error=str(error)[:1000],
                finalizada_en=datetime.now(timezone.utc).isoformat(),
            )


def _es_url_r2(url: str) -> bool:
    base = urlsplit(settings.R2_PUBLIC_BASE_URL).hostname if settings.R2_PUBLIC_BASE_URL else None
    parsed = urlsplit(url)
    return bool(base and parsed.scheme == "https" and parsed.hostname == base)


def _referencias(db: Session) -> list[dict]:
    """Una referencia por fila de galería y por principal sin fila equivalente."""
    imagenes = list(db.scalars(
        select(ImagenProducto).options(selectinload(ImagenProducto.producto)).order_by(ImagenProducto.id)
    ).all())
    por_id = {imagen.id: imagen for imagen in imagenes}
    urls_galeria = {(imagen.producto_id, imagen.url) for imagen in imagenes}
    filas = [
        {
            "imagen_id": imagen.id,
            "producto_id": imagen.producto_id,
            "producto": imagen.producto.nombre if imagen.producto else None,
            "url": imagen.url,
            "contenido": imagen.contenido,
            "media_type": imagen.media_type,
        }
        for imagen in imagenes
    ]
    principales = db.scalars(select(Producto).where(Producto.imagen_url.is_not(None))).all()
    for producto in principales:
        if producto.imagen_url and (producto.id, producto.imagen_url) not in urls_galeria:
            respaldo = None
            if producto.imagen_url.startswith("db:"):
                try:
                    respaldo = por_id.get(int(producto.imagen_url.removeprefix("db:")))
                except ValueError:
                    respaldo = None
            filas.append({
                "imagen_id": None,
                "producto_id": producto.id,
                "producto": producto.nombre,
                "url": producto.imagen_url,
                "contenido": respaldo.contenido if respaldo else None,
                "media_type": respaldo.media_type if respaldo else None,
            })
    return filas


def _leer_remota(url: str) -> tuple[bytes, str | None]:
    """Lee como máximo el límite configurado, sin confiar en Content-Length."""
    total = 0
    partes: list[bytes] = []
    with httpx.stream("GET", url, timeout=20.0, follow_redirects=True) as respuesta:
        respuesta.raise_for_status()
        for parte in respuesta.iter_bytes():
            total += len(parte)
            if total > settings.IMAGENES_DESCARGA_MAX_BYTES:
                raise ValueError("La imagen supera el límite seguro de descarga.")
            partes.append(parte)
        return b"".join(partes), respuesta.headers.get("content-type")


def _inspeccionar_remota(url: str) -> tuple[int, str | None]:
    """Devuelve peso y tipo sin descargar el cuerpo cuando el origen lo informa."""
    if _es_url_r2(url) and r2_imagenes_configurado():
        datos = _cliente_r2().head_object(
            Bucket=settings.R2_BUCKET_NAME,
            Key=unquote(urlsplit(url).path.lstrip("/")),
        )
        return int(datos.get("ContentLength", 0)), datos.get("ContentType")
    respuesta = httpx.head(url, timeout=15.0, follow_redirects=True)
    if respuesta.status_code >= 400:
        respuesta.raise_for_status()
    peso = respuesta.headers.get("content-length")
    return int(peso) if peso and peso.isdigit() else -1, respuesta.headers.get("content-type")


def _detalle_pesada(referencia: dict, contenido: bytes, media_type: str | None) -> dict:
    try:
        with Image.open(BytesIO(contenido)) as imagen:
            imagen.load()
            ancho, alto = imagen.size
            formato = (imagen.format or "desconocido").upper()
        optimizada = procesar_imagen_catalogo(contenido, media_type_declarado=media_type.split(";", 1)[0] if media_type else None)
        ahorro = max(len(contenido) - optimizada.peso, 0)
        return {
            "imagen_id": referencia["imagen_id"],
            "producto_id": referencia["producto_id"],
            "producto": referencia["producto"],
            "url": referencia["url"],
            "peso_bytes": len(contenido),
            "peso_mb": round(len(contenido) / 1024 / 1024, 2),
            "ancho": ancho,
            "alto": alto,
            "formato": formato,
            "estimado_webp_bytes": optimizada.peso,
            "ahorro_estimado_bytes": ahorro,
        }
    except (UnidentifiedImageError, OSError, ImagenInvalidaError) as error:
        return {
            "imagen_id": referencia["imagen_id"],
            "producto_id": referencia["producto_id"],
            "producto": referencia["producto"],
            "url": referencia["url"],
            "peso_bytes": len(contenido),
            "error": str(error),
        }


def obtener_diagnostico_avanzado_imagenes_r2(db: Session) -> dict:
    """Ejecuta una auditoría sin cambios sobre el catálogo completo.

    Las dimensiones y estimaciones se calculan sólo para imágenes de más de
    1 MB. Eso mantiene la auditoría liviana y evita descargar el catálogo ya
    optimizado sólo para inspeccionarlo.
    """
    referencias = _referencias(db)
    total_productos = int(db.scalar(select(func.count(Producto.id))) or 0)
    por_host: dict[str, dict] = defaultdict(lambda: {"imagenes": 0, "bytes": 0})
    pesadas: list[dict] = []
    r2 = externas = inaccesibles = 0
    totales_umbral = {str(mb): 0 for mb in UMBRALES}
    peso_total = 0

    resultados_remotos: dict[int, tuple[int, str | None] | Exception] = {}
    with ThreadPoolExecutor(max_workers=settings.IMAGENES_AUDITORIA_CONCURRENCIA) as executor:
        futuros = {
            executor.submit(_inspeccionar_remota, referencia["url"]): indice
            for indice, referencia in enumerate(referencias)
            if not referencia["url"].startswith("db:")
        }
        for futuro in as_completed(futuros):
            indice = futuros[futuro]
            try:
                resultados_remotos[indice] = futuro.result()
            except Exception as error:
                resultados_remotos[indice] = error

    for indice, referencia in enumerate(referencias):
        url = referencia["url"]
        if url.startswith("db:"):
            contenido = referencia["contenido"] or b""
            peso, media_type = len(contenido), referencia["media_type"]
            host = "base-de-datos"
        else:
            host = urlsplit(url).hostname or "sin-host"
            resultado_remoto = resultados_remotos[indice]
            if isinstance(resultado_remoto, Exception):
                inaccesibles += 1
                por_host[host]["imagenes"] += 1
                por_host[host].setdefault("inaccesibles", 0)
                por_host[host]["inaccesibles"] += 1
                continue
            peso, media_type = resultado_remoto
            if peso < 0:
                try:
                    contenido, media_type_descargado = _leer_remota(url)
                    peso = len(contenido)
                    media_type = media_type_descargado or media_type
                except Exception:
                    inaccesibles += 1
                    por_host[host]["imagenes"] += 1
                    por_host[host].setdefault("inaccesibles", 0)
                    por_host[host]["inaccesibles"] += 1
                    continue
            else:
                contenido = None

        if _es_url_r2(url):
            r2 += 1
        else:
            externas += 1
        peso_total += peso
        por_host[host]["imagenes"] += 1
        por_host[host]["bytes"] += peso
        for umbral in UMBRALES:
            if peso > umbral * 1024 * 1024:
                totales_umbral[str(umbral)] += 1
        if peso > UMBRAL_PESADO:
            try:
                if contenido is None:
                    contenido, media_type_descargado = _leer_remota(url)
                    media_type = media_type_descargado or media_type
                pesadas.append(_detalle_pesada(referencia, contenido, media_type))
            except Exception as error:
                pesadas.append({
                    "imagen_id": referencia["imagen_id"], "producto_id": referencia["producto_id"],
                    "producto": referencia["producto"], "url": url, "peso_bytes": peso,
                    "error": str(error),
                })

    ahorro = sum(int(item.get("ahorro_estimado_bytes") or 0) for item in pesadas)
    estimado = max(peso_total - ahorro, 0)
    return {
        "solo_lectura": True,
        "productos_total": total_productos,
        "imagenes_total": len(referencias),
        "urls_r2": r2,
        "urls_externas_o_backend": externas,
        "imagenes_inaccesibles": inaccesibles,
        "mayores_a_mb": totales_umbral,
        "peso_total_bytes": peso_total,
        "peso_total_mb": round(peso_total / 1024 / 1024, 2),
        "peso_total_gb": round(peso_total / 1024 / 1024 / 1024, 3),
        "por_proveedor": [
            {"hostname": host, "imagenes": datos["imagenes"], "bytes": datos["bytes"],
             "mb": round(datos["bytes"] / 1024 / 1024, 2), "inaccesibles": datos.get("inaccesibles", 0)}
            for host, datos in sorted(por_host.items(), key=lambda item: item[1]["bytes"], reverse=True)
        ],
        "imagenes_pesadas": sorted(pesadas, key=lambda item: int(item.get("peso_bytes") or 0), reverse=True),
        "peso_estimado_optimizado_bytes": estimado,
        "ahorro_estimado_bytes": ahorro,
        "ahorro_estimado_mb": round(ahorro / 1024 / 1024, 2),
        "ahorro_estimado_porcentaje": round((ahorro / peso_total * 100), 1) if peso_total else 0,
    }
