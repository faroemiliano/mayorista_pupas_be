from io import BytesIO
from datetime import datetime, timedelta, timezone
from urllib.parse import urlsplit

import cloudinary
import cloudinary.uploader
from cloudinary.exceptions import Error as CloudinaryError
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.core.config import settings
from app.database.session import SessionLocal
from app.models.imagen_producto import ImagenProducto
from app.models.migracion_woocommerce import MigracionWooCommerce
from app.integrations.woocommerce.urls import es_url_wordpress, url_desde_origen_wordpress
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


def _url_segura_cloudinary(respuesta: dict) -> str:
    url = respuesta.get("secure_url")
    cloud_name = urlsplit(settings.CLOUDINARY_URL).hostname
    parsed = urlsplit(url) if isinstance(url, str) else None
    if not (
        parsed
        and parsed.scheme == "https"
        and parsed.hostname == "res.cloudinary.com"
        and cloud_name
        and parsed.path.startswith(f"/{cloud_name}/")
    ):
        raise ValueError("Cloudinary no devolvió una URL segura de imagen.")
    return url


def subir_imagen_producto_a_cloudinary(
    *, contenido: bytes, producto_id: int, imagen_id: int, nombre: str
) -> str:
    """Guarda una imagen nueva del panel en la cuenta propia de Cloudinary."""
    _configurar_cloudinary()
    respuesta = cloudinary.uploader.upload(
        BytesIO(contenido),
        public_id=f"pupas/catalogo/productos/{producto_id}/imagenes/{imagen_id}",
        resource_type="image",
        overwrite=True,
        unique_filename=False,
        filename_override=nombre,
        tags=["pupas", "catalogo", "carga-panel"],
    )
    return _url_segura_cloudinary(respuesta)


def _es_imagen_wordpress(url: str) -> bool:
    parsed = urlsplit(url)
    return es_url_wordpress(url) and "/wp-content/uploads/" in parsed.path


def _cantidad_imagenes_pendientes(db: Session) -> int:
    return db.scalar(select(func.count(ImagenProducto.id)).where(
        ImagenProducto.url.like("%/wp-content/uploads/%"),
    )) or 0


def _imagenes_pendientes(
    db: Session, *, despues_de_id: int = 0, limite: int | None = None
) -> list[ImagenProducto]:
    consulta = select(ImagenProducto).options(selectinload(ImagenProducto.producto)).where(
        ImagenProducto.url.like("%/wp-content/uploads/%"),
        ImagenProducto.id > despues_de_id,
    ).order_by(ImagenProducto.id)
    if limite is not None:
        consulta = consulta.limit(limite)
    imagenes = db.scalars(consulta).all()
    return [imagen for imagen in imagenes if _es_imagen_wordpress(imagen.url)]


def _subir_imagen(imagen: ImagenProducto) -> str:
    respuesta = cloudinary.uploader.upload(
        url_desde_origen_wordpress(imagen.url),
        public_id=f"pupas/wordpress/productos/{imagen.producto_id}/imagenes/{imagen.id}",
        resource_type="image",
        overwrite=True,
        unique_filename=False,
        tags=["pupas", "wordpress-migracion"],
    )
    return _url_segura_cloudinary(respuesta)


def obtener_diagnostico_imagenes(db: Session) -> dict:
    total = db.scalar(select(func.count(ImagenProducto.id))) or 0
    wordpress = _cantidad_imagenes_pendientes(db)
    cloudinary_count = db.scalar(select(func.count(ImagenProducto.id)).where(
        ImagenProducto.url.like("https://res.cloudinary.com/%"),
    )) or 0
    base_datos = db.scalar(select(func.count(ImagenProducto.id)).where(
        ImagenProducto.url.like("db:%"),
    )) or 0
    return {
        "total": total,
        "wordpress": wordpress,
        "cloudinary": cloudinary_count,
        "base_datos": base_datos,
        "otros": max(total - wordpress - cloudinary_count - base_datos, 0),
        "independiente_wordpress": wordpress == 0,
    }


def preparar_migracion_imagenes_cloudinary(db: Session, limite: int | None = None) -> dict:
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
    pendientes = _cantidad_imagenes_pendientes(db)
    programadas = min(pendientes, limite) if limite else pendientes
    return _estado(
        db, estado="en_progreso", progreso={"pendientes": pendientes, "programadas": programadas, "copiadas": 0, "fallidas": 0},
        resultado=None, error=None, errores=[], iniciada_en=datetime.now(timezone.utc).isoformat(), finalizada_en=None,
    )


def migrar_imagenes_a_cloudinary(db: Session, progreso=None, limite: int | None = None) -> dict:
    try:
        _configurar_cloudinary()
        pendientes_iniciales = _cantidad_imagenes_pendientes(db)
        total = min(pendientes_iniciales, limite) if limite else pendientes_iniciales
        copiadas = fallidas = 0
        procesadas = 0
        ultimo_id = 0
        errores: list[dict[str, str | int]] = []
        while procesadas < total:
            cantidad_lote = min(10, total - procesadas)
            imagenes = _imagenes_pendientes(
                db, despues_de_id=ultimo_id, limite=cantidad_lote
            )
            if not imagenes:
                break
            for imagen in imagenes:
                ultimo_id = imagen.id
                url_original = imagen.url
                try:
                    nueva_url = _subir_imagen(imagen)
                    imagen.origen_url = imagen.origen_url or url_original
                    imagen.url = nueva_url
                    if imagen.producto and (imagen.principal or imagen.producto.imagen_url == url_original):
                        imagen.producto.imagen_url = nueva_url
                    copiadas += 1
                except (CloudinaryError, ValueError) as error:
                    fallidas += 1
                    if len(errores) < 50:
                        errores.append({"imagen_id": imagen.id, "error": str(error)[:300]})
                procesadas += 1
            db.commit()
            avance = {
                "total": total, "procesadas": procesadas, "pendientes": total - procesadas,
                "copiadas": copiadas, "fallidas": fallidas,
            }
            _estado(db, estado="en_progreso", progreso=avance, errores=errores)
            if progreso:
                progreso(avance)
        resultado = {
            "procesadas": procesadas, "copiadas": copiadas, "fallidas": fallidas,
            "pendientes_para_reintentar": _cantidad_imagenes_pendientes(db),
            "prueba": limite is not None,
        }
        _estado(db, estado="completada", error=None, errores=errores, progreso=None,
                resultado=resultado, finalizada_en=datetime.now(timezone.utc).isoformat())
        return resultado
    except Exception as error:
        db.rollback()
        _estado(db, estado="error", error=str(error)[:1000], finalizada_en=datetime.now(timezone.utc).isoformat())
        raise


def ejecutar_migracion_imagenes_cloudinary_background(limite: int | None = None) -> None:
    with SessionLocal() as db:
        migrar_imagenes_a_cloudinary(db, limite=limite)
