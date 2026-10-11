from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import require_admin, require_cliente
from app.database.session import get_db
from app.models.resena_cliente import ResenaCliente
from app.models.usuario import Usuario
from app.schemas.resena_schemas import ResenaCrearRequest, ResenaModeracionRequest, ResenaResponse


router = APIRouter(prefix="/api/resenas", tags=["Reseñas"])


def _nombre_publico(resena: ResenaCliente) -> str:
    nombre = (resena.nombre or "").strip()
    apellido = (resena.apellido or "").strip()
    if not nombre:
        return "Cliente Pupas"
    return f"{nombre} {apellido[:1]}.".strip() if apellido else nombre


def _respuesta(resena: ResenaCliente, usuario: Usuario | None = None, incluir_email: bool = False) -> dict:
    return {
        "id": resena.id,
        "nombre": resena.nombre,
        "apellido": resena.apellido,
        "calificacion": resena.calificacion,
        "comentario": resena.comentario,
        "estado": resena.estado,
        "destacada": resena.destacada,
        "creada_en": resena.creada_en,
        "cliente_nombre": f"{usuario.nombre} {usuario.apellido}".strip() if usuario and incluir_email else _nombre_publico(resena),
        "cliente_email": usuario.email if usuario and incluir_email else None,
    }


@router.get("/publicas", response_model=list[ResenaResponse])
def listar_publicas(limit: int = Query(6, ge=1, le=12), db: Session = Depends(get_db)):
    rows = db.execute(
        select(ResenaCliente, Usuario)
        .join(Usuario, Usuario.id == ResenaCliente.usuario_id)
        .where(ResenaCliente.estado == "aprobada")
        .order_by(ResenaCliente.destacada.desc(), ResenaCliente.creada_en.desc())
        .limit(limit)
    ).all()
    return [_respuesta(resena, usuario) for resena, usuario in rows]


@router.get("/mia", response_model=ResenaResponse | None)
def obtener_mia(db: Session = Depends(get_db), usuario: Usuario = Depends(require_cliente)):
    resena = db.scalar(select(ResenaCliente).where(ResenaCliente.usuario_id == usuario.id))
    return _respuesta(resena, usuario) if resena else None


@router.post("/mia", response_model=ResenaResponse, status_code=status.HTTP_201_CREATED)
def guardar_mia(data: ResenaCrearRequest, db: Session = Depends(get_db), usuario: Usuario = Depends(require_cliente)):
    resena = db.scalar(select(ResenaCliente).where(ResenaCliente.usuario_id == usuario.id))
    if resena is None:
        resena = ResenaCliente(
            usuario_id=usuario.id,
            nombre=data.nombre.strip() if data.nombre and data.nombre.strip() else None,
            apellido=data.apellido.strip() if data.apellido and data.apellido.strip() else None,
            calificacion=data.calificacion,
            comentario=data.comentario.strip(),
        )
        db.add(resena)
    else:
        resena.calificacion = data.calificacion
        resena.comentario = data.comentario.strip()
        resena.nombre = data.nombre.strip() if data.nombre and data.nombre.strip() else None
        resena.apellido = data.apellido.strip() if data.apellido and data.apellido.strip() else None
        resena.estado = "pendiente"
        resena.destacada = False
    db.commit()
    db.refresh(resena)
    return _respuesta(resena, usuario)


@router.get("/admin", response_model=list[ResenaResponse])
def listar_admin(
    estado: str | None = Query(None, pattern="^(pendiente|aprobada|rechazada)$"),
    db: Session = Depends(get_db),
    _: Usuario = Depends(require_admin),
):
    query = select(ResenaCliente, Usuario).join(Usuario, Usuario.id == ResenaCliente.usuario_id)
    if estado:
        query = query.where(ResenaCliente.estado == estado)
    rows = db.execute(query.order_by(ResenaCliente.estado.asc(), ResenaCliente.creada_en.desc()).limit(200)).all()
    return [_respuesta(resena, usuario, incluir_email=True) for resena, usuario in rows]


@router.patch("/admin/{resena_id}", response_model=ResenaResponse)
def moderar(
    resena_id: int,
    data: ResenaModeracionRequest,
    db: Session = Depends(get_db),
    _: Usuario = Depends(require_admin),
):
    resena = db.get(ResenaCliente, resena_id)
    if resena is None:
        raise HTTPException(status_code=404, detail="La opinión no existe.")
    if data.estado is not None:
        resena.estado = data.estado
        if data.estado != "aprobada":
            resena.destacada = False
    if data.destacada is not None:
        resena.destacada = data.destacada if resena.estado == "aprobada" else False
    db.commit()
    db.refresh(resena)
    usuario = db.get(Usuario, resena.usuario_id)
    return _respuesta(resena, usuario, incluir_email=True)
