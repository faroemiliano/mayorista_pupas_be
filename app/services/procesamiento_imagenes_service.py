"""Validación y normalización segura de fotos de catálogo.

Este módulo no conoce la base de datos ni R2. Recibe bytes, comprueba que sean
una imagen real y devuelve una copia WebP sin EXIF/GPS lista para subir.
"""

from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO

from PIL import Image, ImageOps, UnidentifiedImageError

from app.core.config import settings


class ImagenInvalidaError(ValueError):
    """La carga no es una imagen de catálogo segura."""


_MIME_POR_FORMATO = {
    "JPEG": "image/jpeg",
    "PNG": "image/png",
    "WEBP": "image/webp",
}


@dataclass(frozen=True)
class ImagenProcesada:
    contenido: bytes
    media_type: str
    ancho_original: int
    alto_original: int
    ancho: int
    alto: int
    peso_original: int
    peso: int
    formato_original: str


def _tipo_por_magic_bytes(contenido: bytes) -> str | None:
    if contenido.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if contenido.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if contenido.startswith(b"RIFF") and contenido[8:12] == b"WEBP":
        return "image/webp"
    return None


def procesar_imagen_catalogo(
    contenido: bytes,
    *,
    media_type_declarado: str | None = None,
) -> ImagenProcesada:
    """Devuelve una imagen WebP limpia, orientada y de tamaño acotado.

    No se confía en el ``Content-Type`` declarado: primero se verifica la
    firma y luego Pillow decodifica completamente el archivo. GIF no se acepta
    para no convertir por accidente una animación en una foto estática.
    """
    if not contenido:
        raise ImagenInvalidaError("La imagen está vacía.")
    if len(contenido) > settings.IMAGENES_MAX_BYTES:
        raise ImagenInvalidaError("La imagen supera el tamaño máximo permitido.")

    mime_real = _tipo_por_magic_bytes(contenido)
    if mime_real is None:
        raise ImagenInvalidaError("El archivo no contiene una imagen JPEG, PNG o WebP válida.")
    if media_type_declarado and media_type_declarado != mime_real:
        raise ImagenInvalidaError("El tipo declarado no coincide con el contenido real de la imagen.")

    anterior_maximo = Image.MAX_IMAGE_PIXELS
    Image.MAX_IMAGE_PIXELS = settings.IMAGENES_MAX_PIXELES
    try:
        try:
            with Image.open(BytesIO(contenido)) as verificacion:
                verificacion.verify()
            with Image.open(BytesIO(contenido)) as original:
                if getattr(original, "is_animated", False):
                    raise ImagenInvalidaError("No se permiten imágenes animadas en el catálogo.")
                formato = (original.format or "").upper()
                if formato not in _MIME_POR_FORMATO:
                    raise ImagenInvalidaError("El formato de imagen no está permitido.")
                if _MIME_POR_FORMATO[formato] != mime_real:
                    raise ImagenInvalidaError("El contenido de la imagen es inconsistente.")
                original.load()
                ancho_original, alto_original = original.size
                if ancho_original <= 0 or alto_original <= 0:
                    raise ImagenInvalidaError("La imagen no tiene dimensiones válidas.")

                # Corrige orientación de teléfonos. Al guardar en un buffer
                # nuevo no se copian EXIF, GPS, ICC ni otros metadatos.
                imagen = ImageOps.exif_transpose(original)
                tiene_alpha = (
                    "A" in imagen.getbands()
                    or (imagen.mode in {"P", "LA"} and "transparency" in imagen.info)
                )
                imagen = imagen.convert("RGBA" if tiene_alpha else "RGB")
                imagen.thumbnail(
                    (settings.IMAGENES_LADO_MAXIMO, settings.IMAGENES_LADO_MAXIMO),
                    Image.Resampling.LANCZOS,
                )
                salida = BytesIO()
                imagen.save(
                    salida,
                    format="WEBP",
                    quality=settings.IMAGENES_WEBP_QUALITY,
                    method=6,
                )
                resultado = salida.getvalue()
                if not resultado:
                    raise ImagenInvalidaError("No se pudo optimizar la imagen.")
                return ImagenProcesada(
                    contenido=resultado,
                    media_type="image/webp",
                    ancho_original=ancho_original,
                    alto_original=alto_original,
                    ancho=imagen.width,
                    alto=imagen.height,
                    peso_original=len(contenido),
                    peso=len(resultado),
                    formato_original=formato,
                )
        except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as error:
            raise ImagenInvalidaError("La imagen está dañada o no se puede procesar de forma segura.") from error
    finally:
        Image.MAX_IMAGE_PIXELS = anterior_maximo
