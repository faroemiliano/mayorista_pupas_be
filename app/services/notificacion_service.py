from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.models.notificacion import Notificacion
from app.models.usuario import Usuario


def filtros_cliente_habilitado_para_sitio():
    """Criterio compartido por campañas y métricas del panel de clientes."""
    return (
        Usuario.rol == "cliente",
        Usuario.activo.is_(True),
        Usuario.estado_registro == "aprobado",
        Usuario.requiere_migracion_password.is_(False),
        or_(
            Usuario.password_hash.is_not(None),
            Usuario.google_sub.is_not(None),
        ),
    )


def notificar(db: Session, *, audiencia: str, tipo: str, titulo: str, mensaje: str,
              usuario_id: int | None = None, pedido_id: int | None = None,
              email: str | None = None, enviar_email: bool = False,
              enlace_url: str | None = None) -> Notificacion:
    # Las notificaciones comerciales y de pedidos quedan dentro de la plataforma.
    # El único email permitido es el de recuperación de contraseña, gestionado
    # directamente por authRouter.
    del email, enviar_email
    notificacion = Notificacion(usuario_id=usuario_id, pedido_id=pedido_id, audiencia=audiencia,
                                tipo=tipo, titulo=titulo, mensaje=mensaje, enlace_url=enlace_url,
                                email_destino=None, email_estado="omitido")
    db.add(notificacion)
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
) -> tuple[int, int, list[int]]:
    consulta = select(Usuario).where(*filtros_cliente_habilitado_para_sitio())
    if destinatarios == "seleccionados":
        if not usuario_ids:
            raise ValueError("Seleccioná al menos un cliente.")
        consulta = consulta.where(Usuario.id.in_(set(usuario_ids)))
    usuarios = list(db.scalars(consulta.order_by(Usuario.id)).all())
    if not usuarios:
        raise ValueError("No hay clientes activos y habilitados para esta campaña.")

    notificaciones: list[Notificacion] = []
    for usuario in usuarios:
        notificacion = Notificacion(
            usuario_id=usuario.id,
            audiencia="cliente",
            tipo=tipo,
            titulo=titulo.strip(),
            mensaje=mensaje.strip(),
            email_destino=None,
            email_estado="omitido",
        )
        db.add(notificacion)
        notificaciones.append(notificacion)
    db.commit()
    return len(notificaciones), 0, [item.id for item in notificaciones]
