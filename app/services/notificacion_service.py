import smtplib
from email.message import EmailMessage

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.database.session import SessionLocal
from app.models.notificacion import Notificacion
from app.models.usuario import Usuario


def _enviar_email(destino: str | None, asunto: str, contenido: str) -> tuple[str, str | None]:
    if not settings.SMTP_HABILITADO or not destino:
        return "no_configurado", None
    try:
        mensaje = EmailMessage()
        mensaje["Subject"] = asunto
        mensaje["From"] = settings.SMTP_REMITENTE or settings.SMTP_USUARIO
        mensaje["To"] = destino
        mensaje.set_content(contenido)
        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=10) as smtp:
            smtp.starttls()
            if settings.SMTP_USUARIO:
                smtp.login(settings.SMTP_USUARIO, settings.SMTP_PASSWORD)
            smtp.send_message(mensaje)
        return "enviado", None
    except Exception as error:
        return "error", str(error)[:1000]


def notificar(db: Session, *, audiencia: str, tipo: str, titulo: str, mensaje: str,
              usuario_id: int | None = None, pedido_id: int | None = None,
              email: str | None = None) -> Notificacion:
    notificacion = Notificacion(usuario_id=usuario_id, pedido_id=pedido_id, audiencia=audiencia,
                                tipo=tipo, titulo=titulo, mensaje=mensaje, email_destino=email)
    db.add(notificacion)
    db.commit()
    estado, error = _enviar_email(email, titulo, mensaje)
    notificacion.email_estado = estado
    notificacion.email_error = error
    db.commit()
    db.refresh(notificacion)
    return notificacion


def crear_campana(
    db: Session,
    *,
    tipo: str,
    titulo: str,
    mensaje: str,
    destinatarios: str,
    usuario_ids: list[int],
    enviar_email: bool,
) -> tuple[int, int, list[int]]:
    consulta = select(Usuario).where(
        Usuario.rol == "cliente",
        Usuario.activo.is_(True),
        Usuario.estado_registro == "aprobado",
    )
    if destinatarios == "seleccionados":
        if not usuario_ids:
            raise ValueError("Seleccioná al menos un cliente.")
        consulta = consulta.where(Usuario.id.in_(set(usuario_ids)))
    usuarios = list(db.scalars(consulta.order_by(Usuario.id)).all())
    if not usuarios:
        raise ValueError("No hay clientes aprobados para esta campaña.")

    notificaciones: list[Notificacion] = []
    emails_programados = 0
    for usuario in usuarios:
        recibe_email = enviar_email and usuario.acepta_promociones_email
        notificacion = Notificacion(
            usuario_id=usuario.id,
            audiencia="cliente",
            tipo=tipo,
            titulo=titulo.strip(),
            mensaje=mensaje.strip(),
            email_destino=usuario.email if recibe_email else None,
            email_estado="pendiente" if recibe_email else "omitido",
        )
        db.add(notificacion)
        notificaciones.append(notificacion)
        emails_programados += int(recibe_email)
    db.commit()
    return len(notificaciones), emails_programados, [item.id for item in notificaciones]


def enviar_emails_campana(notificacion_ids: list[int]) -> None:
    if not notificacion_ids:
        return
    with SessionLocal() as db:
        notificaciones = db.scalars(
            select(Notificacion).where(Notificacion.id.in_(notificacion_ids))
        ).all()
        for item in notificaciones:
            if not item.email_destino:
                continue
            contenido = item.mensaje
            if item.enlace_url:
                contenido += f"\n\nVer más: {item.enlace_url}"
            estado, error = _enviar_email(item.email_destino, item.titulo, contenido)
            item.email_estado = estado
            item.email_error = error
        db.commit()
