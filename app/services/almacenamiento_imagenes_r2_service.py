"""Almacenamiento de imágenes de catálogo en Cloudflare R2.

Cloudinary sigue siendo el respaldo durante la transición. R2 se utiliza sólo
cuando todas sus credenciales están configuradas explícitamente en el entorno.
"""

from __future__ import annotations

import logging
from typing import Any
from urllib.parse import quote

from app.core.config import settings
from app.services.migracion_imagenes_cloudinary_service import (
    subir_imagen_producto_a_cloudinary,
)


logger = logging.getLogger(__name__)


class R2ImagenError(ValueError):
    """Error al guardar un archivo en el bucket propio."""


_EXTENSION_POR_MEDIA_TYPE = {
    "image/jpeg": "jpg",
    "image/png": "png",
    "image/webp": "webp",
    "image/gif": "gif",
}


def r2_imagenes_configurado() -> bool:
    return settings.r2_imagenes_configurado


def _cliente_r2() -> Any:
    if not r2_imagenes_configurado():
        raise R2ImagenError("R2 no está configurado para imágenes.")
    try:
        import boto3
        from botocore.config import Config
    except ImportError as error:  # protege los entornos aún no actualizados
        raise R2ImagenError("Falta instalar la dependencia de R2 en el backend.") from error

    return boto3.client(
        "s3",
        endpoint_url=settings.r2_endpoint_url,
        aws_access_key_id=settings.R2_ACCESS_KEY_ID,
        aws_secret_access_key=settings.R2_SECRET_ACCESS_KEY,
        region_name="auto",
        config=Config(signature_version="s3v4", retries={"max_attempts": 3, "mode": "standard"}),
    )


def clave_imagen_producto(*, producto_id: int, imagen_id: int, media_type: str) -> str:
    extension = _EXTENSION_POR_MEDIA_TYPE.get(media_type)
    if extension is None:
        raise R2ImagenError("El formato de imagen no está permitido para R2.")
    return f"pupas/catalogo/productos/{producto_id}/imagenes/{imagen_id}.{extension}"


def url_publica_r2(clave: str) -> str:
    base = settings.R2_PUBLIC_BASE_URL.rstrip("/")
    if not base:
        raise R2ImagenError("Falta configurar la URL pública de R2.")
    return f"{base}/{quote(clave, safe='/')}"


def subir_imagen_producto_a_r2(
    *, contenido: bytes, producto_id: int, imagen_id: int, media_type: str
) -> str:
    """Sube una imagen nueva a R2 y devuelve sólo su URL pública propia."""
    clave = clave_imagen_producto(
        producto_id=producto_id,
        imagen_id=imagen_id,
        media_type=media_type,
    )
    try:
        _cliente_r2().put_object(
            Bucket=settings.R2_BUCKET_NAME,
            Key=clave,
            Body=contenido,
            ContentType=media_type,
            CacheControl="public, max-age=31536000, immutable",
        )
    except Exception as error:
        # boto3 puede no estar disponible al importar este módulo en una
        # instalación antigua; la excepción se transforma en un error claro.
        raise R2ImagenError("No se pudo guardar la imagen en R2.") from error
    return url_publica_r2(clave)


def subir_imagen_producto(
    *, contenido: bytes, producto_id: int, imagen_id: int, nombre: str, media_type: str
) -> str:
    """Prefiere R2 y mantiene Cloudinary como respaldo temporal seguro."""
    if r2_imagenes_configurado():
        try:
            return subir_imagen_producto_a_r2(
                contenido=contenido,
                producto_id=producto_id,
                imagen_id=imagen_id,
                media_type=media_type,
            )
        except R2ImagenError:
            if not settings.CLOUDINARY_URL:
                raise
            logger.exception("Falló la carga en R2; se usará Cloudinary como respaldo.")

    return subir_imagen_producto_a_cloudinary(
        contenido=contenido,
        producto_id=producto_id,
        imagen_id=imagen_id,
        nombre=nombre,
    )
