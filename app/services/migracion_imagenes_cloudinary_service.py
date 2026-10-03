from datetime import datetime, timedelta, timezone
from urllib.parse import urlsplit

import cloudinary
import cloudinary.uploader
from cloudinary.exceptions import Error as CloudinaryError
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.config import settings
from app.database.session import SessionLocal
from app.models.imagen_producto import ImagenProducto
from app.models.migracion_woocommerce import MigracionWooCommerce
from app.services.migracion_woocommerce_service import _guardar


TIPO_ESTADO = "estado_imagenes_cloudinary"
ID_ESTADO = "catalogo"


def _estado(db: Session, **cambios) -> dict:
    fila = db.scalar(select(MigracionWooCommerce).where(
        MigracionWooCommerce.tipo == TIPO_ESTADO,
        MigracionWooCommerce.id_externo == ID_ESTADO,
    ))
    datos = dict(fila.datos) if fila else {}
    datos.update(cambios)
    _guardar(db, TIPO_ESTADO, ID_ESTADO, datos)
    return datos


def obtener_estado_migracion_imagenes(db: Session) -> dict:
    fila = db.scalar(select(MigracionWooCommerce).where(
        MigracionWooCommerce.tipo == TIPO_ESTADO,
        MigracionWooCommerce.id_externo == ID_ESTADO,
    ))
    if fila is None:
        return {"estado": "pendiente", "progreso": None, "resultado": None, "error": None, "actualizado_en": None}
    datos = dict(fila.datos)
    datos["actualizado_en"] = fila.actualizado_en.isoformat() if fila.actualizado_en else None
    return datos


def _configurar_cloudinary() -> None:
    datos = urlsplit(settings.CLOUDINARY_URL)
    if not (datos.scheme == "cloudinary" and datos.hostname and datos.username and datos.password):
        raise ValueError("Cloudinary no está configurado. Revisá CLOUDINARY_URL en el backend.")
    cloudinary.config(
        cloud_name=datos.hostname, api_key=datos.username, api_secret=datos.password, secure=True,
    )


def _es_imagen_wordpress(url: str) -> bool:
    parsed = urlsplit(url)
    host_wordpress = urlsplit(settings.WOOCOMMERCE_URL).hostname
    return parsed.scheme == "https" and parsed.hostname == host_wordpress and "/wp-content/uploads/" in parsed.path


def _imagenes_pendientes(db: Session) -> list[ImagenProducto]:
    imagenes = db.scalars(select(ImagenProducto).options(selectinload(ImagenProducto.producto)).where(
        ImagenProducto.url.like("%/wp-content/uploads/%"),
    ).order_by(ImagenProducto.id)).all()
    return [imagen for imagen in imagenes if _es_imagen_wordpress(imagen.url)]


def _subir_imagen(imagen: ImagenProducto) -> str:
    respuesta = cloudinary.uploader.upload(
        imagen.url,
        public_id=f"pupas/wordpress/productos/{imagen.producto_id}/imagenes/{imagen.id}",
        resource_type="image",
        overwrite=True,
        unique_filename=False,
        tags=["pupas", "wordpress-migracion"],
    )
    url = respuesta.get("secure_url")
    if not isinstance(url, str) or not url.startswith("https://res.cloudinary.com/"):
        raise ValueError("Cloudinary no devolvió una URL segura de imagen.")
    return url


def preparar_migracion_imagenes_cloudinary(db: Session) -> dict:
    _configurar_cloudinary()
    actual = obtener_estado_migracion_imagenes(db)
    if actual.get("estado") == "en_progreso":
        fila = db.scalar(select(MigracionWooCommerce).where(
            MigracionWooCommerce.tipo == TIPO_ESTADO,
            MigracionWooCommerce.id_externo == ID_ESTADO,
        ))
        actualizado = fila.actualizado_en if fila else None
        if actualizado and actualizado.tzinfo is None:
            actualizado = actualizado.replace(tzinfo=timezone.utc)
        if actualizado and datetime.now(timezone.utc) - actualizado < timedelta(minutes=2):
            raise ValueError("La copia de imágenes a Cloudinary ya está en progreso.")
    return _estado(
        db, estado="en_progreso", progreso={"pendientes": len(_imagenes_pendientes(db)), "copiadas": 0, "fallidas": 0},
        resultado=None, error=None, errores=[], iniciada_en=datetime.now(timezone.utc).isoformat(), finalizada_en=None,
    )


def migrar_imagenes_a_cloudinary(db: Session, progreso=None) -> dict:
    try:
        _configurar_cloudinary()
        imagenes = _imagenes_pendientes(db)
        total = len(imagenes)
        copiadas = fallidas = 0
        errores: list[dict[str, str | int]] = []
        for indice, imagen in enumerate(imagenes, start=1):
            url_original = imagen.url
            try:
                imagen.url = _subir_imagen(imagen)
                if imagen.producto and (imagen.principal or imagen.producto.imagen_url == url_original):
                    imagen.producto.imagen_url = imagen.url
                copiadas += 1
            except (CloudinaryError, ValueError) as error:
                fallidas += 1
                if len(errores) < 50:
                    errores.append({"imagen_id": imagen.id, "error": str(error)[:300]})
            if indice % 10 == 0 or indice == total:
                db.commit()
                avance = {
                    "total": total, "procesadas": indice, "pendientes": total - indice,
                    "copiadas": copiadas, "fallidas": fallidas,
                }
                _estado(db, estado="en_progreso", progreso=avance, errores=errores)
                if progreso:
                    progreso(avance)
        resultado = {
            "procesadas": total, "copiadas": copiadas, "fallidas": fallidas,
            "pendientes_para_reintentar": len(_imagenes_pendientes(db)),
        }
        _estado(db, estado="completada", error=None, errores=errores, progreso=None,
                resultado=resultado, finalizada_en=datetime.now(timezone.utc).isoformat())
        return resultado
    except Exception as error:
        db.rollback()
        _estado(db, estado="error", error=str(error)[:1000], finalizada_en=datetime.now(timezone.utc).isoformat())
        raise


def ejecutar_migracion_imagenes_cloudinary_background() -> None:
    with SessionLocal() as db:
        migrar_imagenes_a_cloudinary(db)
