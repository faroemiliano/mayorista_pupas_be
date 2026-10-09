"""Copias controladas de imágenes existentes hacia el bucket propio R2."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from urllib.parse import urlsplit

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.core.config import settings
from app.database.session import SessionLocal
from app.models.imagen_producto import ImagenProducto
from app.models.migracion_woocommerce import MigracionWooCommerce
from app.models.producto import Producto
from app.services.almacenamiento_imagenes_r2_service import (
    R2ImagenError,
    r2_imagenes_configurado,
    subir_imagen_producto_a_r2,
)
from app.services.producto_service import _obtener_imagen_catalogo
from app.services.migracion_woocommerce_service import _guardar


TIPO_ESTADO = "estado_imagenes_r2"
ID_ESTADO = "catalogo"


def _es_url_r2(url: str) -> bool:
    host_r2 = urlsplit(settings.R2_PUBLIC_BASE_URL).hostname if settings.R2_PUBLIC_BASE_URL else None
    parsed = urlsplit(url)
    return parsed.scheme == "https" and host_r2 is not None and parsed.hostname == host_r2


def _estado(db: Session, **cambios) -> dict:
    fila = db.scalar(select(MigracionWooCommerce).where(
        MigracionWooCommerce.tipo == TIPO_ESTADO,
        MigracionWooCommerce.id_externo == ID_ESTADO,
    ))
    datos = dict(fila.datos) if fila else {}
    datos.update(cambios)
    _guardar(db, TIPO_ESTADO, ID_ESTADO, datos)
    return datos


def obtener_estado_migracion_imagenes_r2(db: Session) -> dict:
    fila = db.scalar(select(MigracionWooCommerce).where(
        MigracionWooCommerce.tipo == TIPO_ESTADO,
        MigracionWooCommerce.id_externo == ID_ESTADO,
    ))
    if fila is None:
        return {"estado": "pendiente", "progreso": None, "resultado": None, "error": None}
    return dict(fila.datos)


def _pendientes(db: Session, despues_de_id: int, limite: int) -> list[ImagenProducto]:
    base = settings.R2_PUBLIC_BASE_URL.rstrip("/")
    return list(db.scalars(
        select(ImagenProducto)
        .options(selectinload(ImagenProducto.producto))
        .where(ImagenProducto.id > despues_de_id, ~ImagenProducto.url.like(f"{base}/%"))
        .order_by(ImagenProducto.id)
        .limit(limite)
    ).all())


def _filtros_principales_directas(base: str):
    tiene_fila_equivalente = select(ImagenProducto.id).where(
        ImagenProducto.producto_id == Producto.id,
        ImagenProducto.url == Producto.imagen_url,
    ).exists()
    return (
        Producto.imagen_url.is_not(None),
        ~Producto.imagen_url.like(f"{base}/%"),
        ~tiene_fila_equivalente,
    )


def _principales_pendientes(db: Session, despues_de_id: int, limite: int) -> list[Producto]:
    """Productos cuya imagen principal antigua todavía pasa por el backend.

    Algunos productos importados desde Dux sólo tienen ``imagen_url`` y no un
    registro en ``imagenes_productos``. La migración original no los incluía,
    por lo que el frontend debía usar /api/productos/{id}/imagen como proxy.
    """
    base = settings.R2_PUBLIC_BASE_URL.rstrip("/")
    return list(db.scalars(
        select(Producto)
        .where(
            Producto.id > despues_de_id,
            *_filtros_principales_directas(base),
        )
        .order_by(Producto.id)
        .limit(limite)
    ).all())


def _migrar_principal_directa(producto: Producto) -> bool:
    """Copia a R2 una imagen principal que no posee fila de galería."""
    if not producto.imagen_url or _es_url_r2(producto.imagen_url):
        return False
    if producto.imagen_url.startswith("db:"):
        # Los datos binarios se migran a través de su fila ImagenProducto.
        return False

    contenido, media_type = _obtener_imagen_catalogo(producto.imagen_url)
    producto.imagen_url = subir_imagen_producto_a_r2(
        contenido=contenido,
        producto_id=producto.id,
        # 0 se reserva para la imagen principal histórica sin registro propio.
        imagen_id=0,
        media_type=media_type,
    )
    return True


def preparar_migracion_imagenes_r2(db: Session) -> dict:
    if not r2_imagenes_configurado():
        raise R2ImagenError("R2 no está configurado en el backend.")
    actual = obtener_estado_migracion_imagenes_r2(db)
    if actual.get("estado") == "en_progreso":
        raise ValueError("La migración de imágenes a R2 ya está en progreso.")
    base = settings.R2_PUBLIC_BASE_URL.rstrip("/")
    diagnostico = obtener_diagnostico_migracion_imagenes_r2(db)
    pendientes = diagnostico["total_pendientes"]
    return _estado(db, estado="en_progreso", progreso={"total": pendientes, "procesadas": 0, "copiadas": 0, "fallidas": 0}, resultado=None, error=None, errores=[], iniciada_en=datetime.now(timezone.utc).isoformat())


def obtener_diagnostico_migracion_imagenes_r2(db: Session) -> dict:
    """Cantidad exacta a copiar antes de iniciar una migración a R2."""
    base = settings.R2_PUBLIC_BASE_URL.rstrip("/")
    galeria = db.scalar(
        select(func.count(ImagenProducto.id)).where(~ImagenProducto.url.like(f"{base}/%"))
    ) or 0
    principales_directas = db.scalar(
        select(func.count(Producto.id)).where(*_filtros_principales_directas(base))
    ) or 0
    return {
        "imagenes_galeria_pendientes": int(galeria),
        "principales_directas_pendientes": int(principales_directas),
        "total_pendientes": int(galeria + principales_directas),
    }


def migrar_imagenes_a_r2(db: Session) -> dict:
    """Migra de a cinco imágenes para mantener bajo el uso de memoria."""
    estado = obtener_estado_migracion_imagenes_r2(db)
    total = int((estado.get("progreso") or {}).get("total") or 0)
    procesadas = copiadas = fallidas = ultimo_id = 0
    errores: list[dict[str, str | int]] = []
    try:
        while True:
            lote = _pendientes(db, ultimo_id, 5)
            if not lote:
                break
            for imagen in lote:
                ultimo_id = imagen.id
                anterior = imagen.url
                try:
                    contenido, media_type = (imagen.contenido, imagen.media_type or "image/jpeg") if imagen.contenido is not None else _obtener_imagen_catalogo(anterior)
                    nueva = subir_imagen_producto_a_r2(contenido=contenido, producto_id=imagen.producto_id, imagen_id=imagen.id, media_type=media_type)
                    imagen.respaldo_url = imagen.respaldo_url or anterior
                    imagen.url = nueva
                    if imagen.producto and (imagen.principal or imagen.producto.imagen_url == anterior):
                        imagen.producto.imagen_url = nueva
                    copiadas += 1
                except Exception as error:
                    fallidas += 1
                    if len(errores) < 50:
                        errores.append({"imagen_id": imagen.id, "error": str(error)[:300]})
                procesadas += 1
            db.commit()
            _estado(db, estado="en_progreso", progreso={"total": total, "procesadas": procesadas, "copiadas": copiadas, "fallidas": fallidas}, errores=errores)

        # También cubre los productos Dux antiguos cuya única foto vive en
        # productos.imagen_url y que por eso antes se servían desde Render.
        ultimo_producto_id = 0
        while True:
            lote_principales = _principales_pendientes(db, ultimo_producto_id, 5)
            if not lote_principales:
                break
            for producto in lote_principales:
                ultimo_producto_id = producto.id
                try:
                    if _migrar_principal_directa(producto):
                        copiadas += 1
                except Exception as error:
                    fallidas += 1
                    if len(errores) < 50:
                        errores.append({"producto_id": producto.id, "error": str(error)[:300]})
                procesadas += 1
            db.commit()
            _estado(db, estado="en_progreso", progreso={"total": total, "procesadas": procesadas, "copiadas": copiadas, "fallidas": fallidas}, errores=errores)
        resultado = {"procesadas": procesadas, "copiadas": copiadas, "fallidas": fallidas, "pendientes_para_reintentar": fallidas}
        _estado(db, estado="completada", progreso=None, resultado=resultado, error=None, errores=errores, finalizada_en=datetime.now(timezone.utc).isoformat())
        return resultado
    except Exception as error:
        db.rollback()
        _estado(db, estado="error", error=str(error)[:1000], finalizada_en=datetime.now(timezone.utc).isoformat())
        raise


def ejecutar_migracion_imagenes_r2_background() -> None:
    with SessionLocal() as db:
        migrar_imagenes_a_r2(db)


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

    # Si la imagen principal no estaba en la galería, se copiaba mediante el
    # proxy de Render. Ahora queda directamente en el dominio propio de R2.
    principal_directa = False
    if (
        producto.imagen_url
        and not _es_url_r2(producto.imagen_url)
        and not any(imagen.url == producto.imagen_url for imagen in producto.imagenes)
    ):
        try:
            principal_directa = _migrar_principal_directa(producto)
        except Exception as error:
            return {
                "producto_id": producto.id,
                "producto": producto.nombre,
                "copiadas": 0,
                "omitidas_r2": omitidas,
                "fallidas": 1,
                "errores": [{"producto_id": producto.id, "error": str(error)[:300]}],
                "actualizado": False,
            }
    db.commit()

    return {
        "producto_id": producto.id,
        "producto": producto.nombre,
        "copiadas": len(preparadas) + int(principal_directa),
        "omitidas_r2": omitidas,
        "fallidas": 0,
        "errores": [],
        "actualizado": True,
    }
