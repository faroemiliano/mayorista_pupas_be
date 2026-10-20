import base64
import binascii
from urllib.parse import urlparse

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.core.config import settings
from app.core.security import require_admin_total
from app.database.session import get_db
from app.models.portada_inicio import PortadaInicio
from app.models.imagen_producto import ImagenProducto
from app.models.producto import Producto
from app.models.usuario import Usuario
from app.services.almacenamiento_imagenes_r2_service import (
    R2ImagenError,
    eliminar_imagen_r2_si_corresponde,
    subir_imagen_portada_a_r2,
)


IMAGENES_EDITABLES = frozenset({
    "bikinis",
    "pijamas",
    "lenceria",
    "coleccion-bikinis-1",
    "coleccion-bikinis-2",
    "coleccion-pijamas-1",
    "coleccion-pijamas-2",
})

public_router = APIRouter(prefix="/api/portada", tags=["Portada"])
admin_router = APIRouter(prefix="/api/admin/portada", tags=["Administración - Portada"])


class ImagenPortadaRequest(BaseModel):
    nombre: str = Field(min_length=1, max_length=180)
    media_type: str = Field(pattern=r"^image/(jpeg|png|webp)$")
    contenido_base64: str = Field(min_length=4)


class ImagenProductoPortadaRequest(BaseModel):
    imagen_id: int = Field(gt=0)


def _validar_imagen(data: ImagenPortadaRequest) -> bytes:
    try:
        contenido = base64.b64decode(data.contenido_base64, validate=True)
    except (binascii.Error, ValueError) as error:
        raise HTTPException(422, "La imagen enviada no es válida.") from error
    if len(contenido) > 8 * 1024 * 1024:
        raise HTTPException(413, "La imagen puede pesar hasta 8 MB.")
    firmas = {
        "image/jpeg": contenido.startswith(b"\xff\xd8\xff"),
        "image/png": contenido.startswith(b"\x89PNG\r\n\x1a\n"),
        "image/webp": contenido.startswith(b"RIFF") and contenido[8:12] == b"WEBP",
    }
    if not firmas.get(data.media_type, False):
        raise HTTPException(422, "El contenido no coincide con el formato de imagen.")
    return contenido


def _es_portada_subida_a_r2(url: str | None) -> bool:
    """Sólo las portadas cargadas desde PC son propiedad de esta sección.

    Una foto de catálogo puede compartirse como portada. En ese caso no debe
    borrarse del bucket al cambiar la portada, porque sigue perteneciendo al
    producto original.
    """
    if not url or not settings.R2_PUBLIC_BASE_URL:
        return False
    base = urlparse(settings.R2_PUBLIC_BASE_URL)
    actual = urlparse(url)
    return (
        actual.scheme == "https"
        and actual.hostname == base.hostname
        and actual.path.startswith("/pupas/sitio/portada/")
    )


def _guardar_portada(
    *,
    db: Session,
    slide_id: str,
    imagen_url: str,
    media_type: str,
    usuario_id: int,
    producto_id: int | None = None,
) -> tuple[PortadaInicio, str | None]:
    portada = db.scalar(select(PortadaInicio).where(PortadaInicio.slide_id == slide_id))
    url_anterior = portada.imagen_url if portada else None
    if portada is None:
        portada = PortadaInicio(
            slide_id=slide_id,
            imagen_url=imagen_url,
            media_type=media_type,
        )
        db.add(portada)
    else:
        portada.imagen_url = imagen_url
        portada.media_type = media_type
    portada.producto_id = producto_id
    portada.actualizada_por_id = usuario_id
    db.commit()
    db.refresh(portada)
    return portada, url_anterior


@public_router.get("")
def listar_portadas(db: Session = Depends(get_db)):
    filas = db.scalars(select(PortadaInicio).options(selectinload(PortadaInicio.producto))).all()
    return {
        "imagenes": {fila.slide_id: fila.imagen_url for fila in filas},
        "productos": {
            fila.slide_id: {"id": fila.producto.id, "slug": fila.producto.slug}
            for fila in filas
            if fila.producto is not None
        },
    }


@admin_router.get("/imagenes-producto")
def listar_imagenes_de_catalogo(
    categoria_id: int = Query(gt=0),
    buscar: str = Query(default="", max_length=100),
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=10, ge=1, le=10),
    db: Session = Depends(get_db),
    _: Usuario = Depends(require_admin_total),
):
    """Selector liviano: devuelve exactamente una página de fotos del catálogo."""
    filtros = [
        Producto.categoria_id == categoria_id,
        Producto.habilitado.is_(True),
        Producto.visible_tienda.is_(True),
        ImagenProducto.url.startswith(settings.R2_PUBLIC_BASE_URL.rstrip("/") + "/"),
    ]
    if buscar.strip():
        filtros.append(Producto.nombre.ilike(f"%{buscar.strip()}%"))

    base = select(ImagenProducto, Producto).join(Producto).where(*filtros)
    total = db.scalar(
        select(func.count(ImagenProducto.id)).join(Producto).where(*filtros)
    ) or 0
    filas = db.execute(
        base.order_by(Producto.actualizado_en.desc(), ImagenProducto.orden, ImagenProducto.id)
        .offset((page - 1) * limit)
        .limit(limit)
    ).all()
    return {
        "items": [
            {
                "id": imagen.id,
                "url": imagen.url,
                "producto_id": producto.id,
                "producto_nombre": producto.nombre,
                "producto_slug": producto.slug,
            }
            for imagen, producto in filas
        ],
        "total": total,
        "page": page,
        "limit": limit,
        "total_paginas": max(1, (total + limit - 1) // limit),
    }


@admin_router.put("/{slide_id}")
def actualizar_portada(
    slide_id: str,
    data: ImagenPortadaRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(require_admin_total),
):
    if slide_id not in IMAGENES_EDITABLES:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "La portada seleccionada no existe.")

    contenido = _validar_imagen(data)
    try:
        url = subir_imagen_portada_a_r2(
            contenido=contenido, slide_id=slide_id, media_type=data.media_type
        )
    except R2ImagenError as error:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, str(error)) from error

    portada, url_anterior = _guardar_portada(
        db=db,
        slide_id=slide_id,
        imagen_url=url,
        media_type=data.media_type,
        usuario_id=usuario.id,
        producto_id=None,
    )

    if _es_portada_subida_a_r2(url_anterior):
        background_tasks.add_task(eliminar_imagen_r2_si_corresponde, url_anterior)
    return {"slide_id": portada.slide_id, "imagen_url": portada.imagen_url}


@admin_router.put("/{slide_id}/imagen-producto")
def usar_imagen_de_producto_en_portada(
    slide_id: str,
    data: ImagenProductoPortadaRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(require_admin_total),
):
    if slide_id not in IMAGENES_EDITABLES:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "La portada seleccionada no existe.")

    imagen = db.get(ImagenProducto, data.imagen_id)
    if imagen is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "La imagen de producto no existe.")
    if not imagen.url.startswith(settings.R2_PUBLIC_BASE_URL.rstrip("/") + "/"):
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "Esta foto todavía no está almacenada en R2.",
        )

    portada, url_anterior = _guardar_portada(
        db=db,
        slide_id=slide_id,
        imagen_url=imagen.url,
        media_type=imagen.media_type or "image/jpeg",
        usuario_id=usuario.id,
        producto_id=imagen.producto_id,
    )
    if _es_portada_subida_a_r2(url_anterior):
        background_tasks.add_task(eliminar_imagen_r2_si_corresponde, url_anterior)
    return {"slide_id": portada.slide_id, "imagen_url": portada.imagen_url}
