"""Almacenamiento de imágenes de catálogo en Cloudflare R2.

Cloudinary sigue siendo el respaldo durante la transición. R2 se utiliza sólo
cuando todas sus credenciales están configuradas explícitamente en el entorno.
"""

from __future__ import annotations

import logging
from typing import Any
from urllib.parse import quote, urlsplit
from uuid import uuid4

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

_MAX_TAMANIO_VIDEO_PORTADA = 50 * 1024 * 1024


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


def subir_imagen_portada_a_r2(*, contenido: bytes, slide_id: str, media_type: str) -> str:
    """Guarda una portada del inicio únicamente en el almacenamiento propio R2."""
    extension = _EXTENSION_POR_MEDIA_TYPE.get(media_type)
    if extension is None:
        raise R2ImagenError("El formato de imagen no está permitido para R2.")
    clave = f"pupas/sitio/portada/{slide_id}/{uuid4().hex}.{extension}"
    try:
        _cliente_r2().put_object(
            Bucket=settings.R2_BUCKET_NAME,
            Key=clave,
            Body=contenido,
            ContentType=media_type,
            CacheControl="public, max-age=31536000, immutable",
        )
    except Exception as error:
        raise R2ImagenError("No se pudo guardar la portada en R2.") from error
    return url_publica_r2(clave)


def crear_carga_directa_video_portada(*, video_id: str, media_type: str, tamano: int) -> dict[str, str]:
    """Entrega una URL temporal para cargar un MP4 directamente a R2.

    El navegador sube el archivo al bucket sin atravesar Render, por lo que el
    backend no consume memoria ni ancho de banda del video.
    """
    if media_type != "video/mp4":
        raise R2ImagenError("El video debe estar en formato MP4.")
    if tamano <= 0 or tamano > _MAX_TAMANIO_VIDEO_PORTADA:
        raise R2ImagenError("El video puede pesar hasta 50 MB.")
    clave = f"pupas/sitio/videos/{video_id}/{uuid4().hex}.mp4"
    try:
        upload_url = _cliente_r2().generate_presigned_url(
            "put_object",
            Params={
                "Bucket": settings.R2_BUCKET_NAME,
                "Key": clave,
                "ContentType": media_type,
                "CacheControl": "public, max-age=31536000, immutable",
            },
            ExpiresIn=600,
            HttpMethod="PUT",
        )
    except Exception as error:
        raise R2ImagenError("No se pudo preparar la carga del video en R2.") from error
    return {"clave": clave, "upload_url": upload_url, "video_url": url_publica_r2(clave)}


def confirmar_video_portada_en_r2(*, video_id: str, clave: str) -> str:
    """Confirma que el objeto temporal existe y respeta el límite de tamaño."""
    prefijo = f"pupas/sitio/videos/{video_id}/"
    if not clave.startswith(prefijo) or not clave.endswith(".mp4"):
        raise R2ImagenError("La carga de video no es válida.")
    try:
        datos = _cliente_r2().head_object(Bucket=settings.R2_BUCKET_NAME, Key=clave)
        if int(datos.get("ContentLength", 0)) > _MAX_TAMANIO_VIDEO_PORTADA:
            _cliente_r2().delete_object(Bucket=settings.R2_BUCKET_NAME, Key=clave)
            raise R2ImagenError("El video supera el límite de 50 MB.")
    except R2ImagenError:
        raise
    except Exception as error:
        raise R2ImagenError("No se encontró el video cargado en R2.") from error
    return url_publica_r2(clave)


def eliminar_imagen_r2_si_corresponde(url: str) -> None:
    """Elimina el objeto físico sólo si la URL pertenece al bucket propio."""
    parsed = urlsplit(url)
    base = urlsplit(settings.R2_PUBLIC_BASE_URL).hostname if settings.R2_PUBLIC_BASE_URL else None
    if not (base and parsed.scheme == "https" and parsed.hostname == base):
        return
    clave = parsed.path.lstrip("/")
    if not clave:
        return
    try:
        _cliente_r2().delete_object(Bucket=settings.R2_BUCKET_NAME, Key=clave)
    except Exception:
        # La foto ya fue quitada de la tienda. Un fallo de limpieza nunca debe
        # impedir al administrador borrar su registro.
        logger.exception("No se pudo eliminar una imagen de R2: %s", clave)


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
