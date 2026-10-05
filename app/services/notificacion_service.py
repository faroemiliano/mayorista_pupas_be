import smtplib
import html
from email.message import EmailMessage

import httpx

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.database.session import SessionLocal
from app.models.notificacion import Notificacion
from app.models.usuario import Usuario


def _html_email(asunto: str, contenido: str) -> str:
    parrafos = "".join(
        f'<p style="margin:0 0 14px;line-height:1.65;color:#3f3f46">{html.escape(parrafo)}</p>'
        for parrafo in contenido.split("\n\n") if parrafo.strip()
    )
    return f'''<!doctype html><html><body style="margin:0;background:#f5f5f4;font-family:Arial,sans-serif"><div style="max-width:620px;margin:0 auto;padding:32px 16px"><div style="background:#111;padding:24px 30px;color:#fff"><div style="font-family:Georgia,serif;font-size:30px">Pupas</div><div style="margin-top:5px;font-size:10px;letter-spacing:2px;color:#d4d4d4">MAYORISTA</div></div><div style="background:#fff;padding:30px;border:1px solid #e5e5e5"><h1 style="margin:0 0 22px;font-family:Georgia,serif;font-size:27px;color:#18181b">{html.escape(asunto)}</h1>{parrafos}<p style="margin:28px 0 0;padding-top:20px;border-top:1px solid #e5e5e5;font-size:12px;color:#71717a">Pupas Mayorista · Este es un mensaje automático relacionado con tu pedido.</p></div></div></body></html>'''


def _enviar_email(destino: str | None, asunto: str, contenido: str) -> tuple[str, str | None]:
    if not destino:
        return "no_configurado", None
    if settings.RESEND_API_KEY:
        try:
            response = httpx.post(
                "https://api.resend.com/emails",
                headers={"Authorization": f"Bearer {settings.RESEND_API_KEY}"},
                json={"from": settings.EMAIL_FROM, "to": [destino], "subject": asunto,
                      "text": contenido, "html": _html_email(asunto, contenido)},
                timeout=15,
            )
            response.raise_for_status()
            return "enviado", None
        except httpx.HTTPError as error:
            return "error", str(error)[:1000]
    if not settings.SMTP_HABILITADO:
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
              email: str | None = None, enviar_email: bool = True) -> Notificacion:
    notificacion = Notificacion(usuario_id=usuario_id, pedido_id=pedido_id, audiencia=audiencia,
                                tipo=tipo, titulo=titulo, mensaje=mensaje, email_destino=email)
    db.add(notificacion)
    db.commit()
    estado, error = _enviar_email(email, titulo, mensaje) if enviar_email else ("omitido", None)
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
