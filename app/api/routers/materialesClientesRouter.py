import base64
import binascii
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import require_admin, require_cliente
from app.database.session import get_db
from app.models.material_cliente import MaterialCliente
from app.models.notificacion import Notificacion
from app.models.usuario import Usuario
from app.schemas.material_cliente_schemas import MaterialClienteBatchCreate, MaterialClienteCreate, MaterialClienteResponse


router = APIRouter(prefix="/api/materiales-clientes", tags=["Material para clientes"])
admin_router = APIRouter(
    prefix="/api/admin/materiales-clientes",
    tags=["Administración - Material para clientes"],
    dependencies=[Depends(require_admin)],
)


def _tipo_imagen(contenido: bytes) -> str | None:
    if contenido.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if contenido.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if contenido.startswith((b"GIF87a", b"GIF89a")):
        return "image/gif"
    if contenido.startswith(b"RIFF") and contenido[8:12] == b"WEBP":
        return "image/webp"
    return None


def _listar(db: Session) -> list[MaterialCliente]:
    return list(db.scalars(select(MaterialCliente).order_by(MaterialCliente.creado_en.desc(), MaterialCliente.id.desc())).all())


def _decodificar_imagen(contenido_base64: str) -> tuple[bytes, str]:
    try:
        contenido = base64.b64decode(contenido_base64, validate=True)
    except (binascii.Error, ValueError) as error:
        raise HTTPException(status_code=422, detail="Uno de los archivos enviados no es válido.") from error
    if len(contenido) > 8 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="Cada imagen puede pesar como máximo 8 MB.")
    tipo = _tipo_imagen(contenido)
    if tipo is None:
        raise HTTPException(status_code=422, detail="Solo se permiten imágenes JPG, PNG, GIF o WebP.")
    return contenido, tipo


def _notificar_nuevo_material(db: Session, cantidad: int, titulo: str) -> None:
    clientes = db.scalars(select(Usuario).where(
        Usuario.rol == "cliente", Usuario.activo.is_(True), Usuario.estado_registro == "aprobado"
    )).all()
    mensaje = (
        f"Ya podés descargar “{titulo}” desde Mi cuenta, en Material para tu tienda."
        if cantidad == 1
        else f"Hay {cantidad} nuevas imágenes disponibles en Mi cuenta, dentro de Material para tu tienda."
    )
    for cliente in clientes:
        db.add(Notificacion(
            usuario_id=cliente.id, audiencia="cliente", tipo="material_nuevo",
            titulo="Nuevo material disponible", mensaje=mensaje,
        ))


@router.get("/", response_model=list[MaterialClienteResponse])
def listar_materiales(db: Session = Depends(get_db), usuario: Usuario = Depends(require_cliente)):
    if usuario.rol != "admin" and usuario.estado_registro != "aprobado":
        raise HTTPException(status_code=403, detail="Tu cuenta debe estar aprobada para acceder al material.")
    return _listar(db)


@router.get("/{material_id}/archivo")
def obtener_archivo(material_id: int, descargar: bool = False, db: Session = Depends(get_db), usuario: Usuario = Depends(require_cliente)):
    if usuario.rol != "admin" and usuario.estado_registro != "aprobado":
        raise HTTPException(status_code=403, detail="Tu cuenta debe estar aprobada para acceder al material.")
    material = db.get(MaterialCliente, material_id)
    if material is None:
        raise HTTPException(status_code=404, detail="Imagen no encontrada.")
    disposition = "attachment" if descargar else "inline"
    return Response(
        content=material.contenido,
        media_type=material.tipo_contenido,
        headers={"Content-Disposition": f"{disposition}; filename*=UTF-8''{quote(material.nombre_archivo)}"},
    )


@admin_router.get("/", response_model=list[MaterialClienteResponse])
def listar_materiales_admin(db: Session = Depends(get_db)):
    return _listar(db)


@admin_router.post("/", response_model=MaterialClienteResponse, status_code=status.HTTP_201_CREATED)
def crear_material(data: MaterialClienteCreate, db: Session = Depends(get_db)):
    contenido, tipo = _decodificar_imagen(data.contenido_base64)
    material = MaterialCliente(
        titulo=data.titulo.strip(),
        descripcion=data.descripcion.strip() if data.descripcion and data.descripcion.strip() else None,
        nombre_archivo=data.nombre_archivo.rsplit("/", 1)[-1].rsplit("\\", 1)[-1],
        tipo_contenido=tipo,
        contenido=contenido,
    )
    db.add(material)
    db.flush()
    _notificar_nuevo_material(db, 1, material.titulo)
    db.commit()
    db.refresh(material)
    return material


@admin_router.post("/lote", response_model=list[MaterialClienteResponse], status_code=status.HTTP_201_CREATED)
def crear_materiales_lote(data: MaterialClienteBatchCreate, db: Session = Depends(get_db)):
    decodificados = [_decodificar_imagen(archivo.contenido_base64) for archivo in data.archivos]
    if sum(len(contenido) for contenido, _ in decodificados) > 60 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="El lote completo no puede superar los 60 MB.")
    materiales = []
    for archivo, (contenido, tipo) in zip(data.archivos, decodificados, strict=True):
        material = MaterialCliente(
            titulo=data.titulo.strip(),
            descripcion=data.descripcion.strip() if data.descripcion and data.descripcion.strip() else None,
            nombre_archivo=archivo.nombre_archivo.rsplit("/", 1)[-1].rsplit("\\", 1)[-1],
            tipo_contenido=tipo,
            contenido=contenido,
        )
        db.add(material)
        materiales.append(material)
    _notificar_nuevo_material(db, len(materiales), data.titulo.strip())
    db.commit()
    for material in materiales:
        db.refresh(material)
    return materiales


@admin_router.delete("/{material_id}", status_code=status.HTTP_204_NO_CONTENT)
def eliminar_material(material_id: int, db: Session = Depends(get_db)):
    material = db.get(MaterialCliente, material_id)
    if material is None:
        raise HTTPException(status_code=404, detail="Imagen no encontrada.")
    db.delete(material)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
