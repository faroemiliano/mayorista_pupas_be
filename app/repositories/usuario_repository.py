from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.usuario import Usuario


def get_usuario_by_google_sub(db: Session, google_sub: str) -> Usuario | None:
    return db.scalar(select(Usuario).where(Usuario.google_sub == google_sub))


def get_usuario_by_id(db: Session, usuario_id: int) -> Usuario | None:
    return db.get(Usuario, usuario_id)


def get_usuario_by_email(db: Session, email: str) -> Usuario | None:
    return db.scalar(select(Usuario).where(Usuario.email == email.lower()))
