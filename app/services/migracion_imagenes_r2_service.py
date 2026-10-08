"""Copias controladas de imágenes existentes hacia el bucket propio R2."""

from __future__ import annotations

from urllib.parse import urlsplit

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.config import settings
from app.models.imagen_producto import ImagenProducto
from app.models.producto import Producto
from app.services.almacenamiento_imagenes_r2_service import (
    R2ImagenError,
    r2_imagenes_configurado,
    subir_imagen_producto_a_r2,
)
from app.services.producto_service import _obtener_imagen_catalogo


def _es_url_r2(url: str) -> bool:
    host_r2 = urlsplit(settings.R2_PUBLIC_BASE_URL).hostname if settings.R2_PUBLIC_BASE_URL else None
    parsed = urlsplit(url)
    return parsed.scheme == "https" and host_r2 is not None and parsed.hostname == host_r2


def migrar_imagenes_producto_a_r2(db: Session, producto_id: int) -> dict:
    """Copia todas las fotos de un producto, sin borrar el proveedor anterior.

    Primero carga todos los archivos a R2. Sólo si no hay errores actualiza las
    URL de la base en una única transacción, evitando productos a medio migrar.
    """
    if not r2_imagenes_configurado():
        raise R2ImagenError("R2 no está configurado en el backend.")

    producto = db.scalar(
        select(Producto)
        .options(selectinload(Producto.imagenes))
        .where(Producto.id == producto_id)
    )
    if producto is None:
        raise ValueError("Producto no encontrado.")

    pendientes = [imagen for imagen in producto.imagenes if not _es_url_r2(imagen.url)]
    omitidas = len(producto.imagenes) - len(pendientes)
    preparadas: list[tuple[ImagenProducto, str, str]] = []
    errores: list[dict[str, str | int]] = []

    for imagen in pendientes:
        try:
            if imagen.contenido is not None:
                contenido = imagen.contenido
                media_type = imagen.media_type or "image/jpeg"
            else:
                contenido, media_type = _obtener_imagen_catalogo(imagen.url)
            nueva_url = subir_imagen_producto_a_r2(
                contenido=contenido,
                producto_id=producto.id,
                imagen_id=imagen.id,
                media_type=media_type,
            )
            preparadas.append((imagen, imagen.url, nueva_url))
        except Exception as error:
            errores.append({"imagen_id": imagen.id, "error": str(error)[:300]})

    # Si una foto falló, las URLs del producto siguen intactas y el administrador
    # puede corregir el problema antes de reintentar.
    if errores:
        return {
            "producto_id": producto.id,
            "producto": producto.nombre,
            "copiadas": 0,
            "omitidas_r2": omitidas,
            "fallidas": len(errores),
            "errores": errores,
            "actualizado": False,
        }

    for imagen, url_anterior, nueva_url in preparadas:
        imagen.respaldo_url = imagen.respaldo_url or url_anterior
        imagen.url = nueva_url
        if imagen.principal or producto.imagen_url == url_anterior:
            producto.imagen_url = nueva_url
    db.commit()

    return {
        "producto_id": producto.id,
        "producto": producto.nombre,
        "copiadas": len(preparadas),
        "omitidas_r2": omitidas,
        "fallidas": 0,
        "errores": [],
        "actualizado": True,
    }
