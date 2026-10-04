from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.migracion_woocommerce import MigracionWooCommerce
from app.models.usuario import Usuario
from app.models.usuario_wordpress import UsuarioWordpress


def _texto(*valores) -> str | None:
    for valor in valores:
        if valor is not None and str(valor).strip():
            return str(valor).strip()
    return None


def _fecha(valor: str | None) -> datetime | None:
    if not valor:
        return None
    try:
        return datetime.fromisoformat(valor.replace("Z", "+00:00"))
    except ValueError:
        return None


def _debe_completar_nombre(usuario: Usuario) -> bool:
    """No reemplaza un nombre que el cliente ya corrigió en esta tienda."""
    nombre = (usuario.nombre or "").strip().casefold()
    return not nombre or nombre == "cliente" or nombre == usuario.email.split("@", 1)[0].casefold()


def convertir_clientes_wordpress(db: Session, progreso=None) -> dict:
    filas = list(db.scalars(
        select(MigracionWooCommerce)
        .where(MigracionWooCommerce.tipo == "cliente")
        .order_by(MigracionWooCommerce.id.asc())
    ).all())
    resultado = {
        "procesados": 0, "creados": 0, "vinculados": 0,
        "sin_email": 0, "emails_repetidos": 0,
    }
    emails_vistos: set[str] = set()
    for fila in filas:
        datos = fila.datos
        facturacion = datos.get("billing") or {}
        email = (_texto(datos.get("email"), facturacion.get("email")) or "").lower()
        if not email or "@" not in email:
            resultado["sin_email"] += 1
            resultado["procesados"] += 1
            continue
        wordpress_id = int(datos["id"])
        nombre_wordpress = _texto(
            datos.get("first_name"), facturacion.get("first_name"), datos.get("username"),
        )
        apellido_wordpress = _texto(datos.get("last_name"), facturacion.get("last_name"))
        repetido = email in emails_vistos
        if repetido:
            resultado["emails_repetidos"] += 1
        emails_vistos.add(email)

        usuario = db.scalar(select(Usuario).where(Usuario.wordpress_id == wordpress_id))
        if usuario is None:
            usuario = db.scalar(select(Usuario).where(Usuario.email == email))
        creado = usuario is None
        if creado:
            usuario = Usuario(
                wordpress_id=wordpress_id,
                origen="wordpress",
                email=email,
                nombre=nombre_wordpress or "Cliente",
                apellido=apellido_wordpress or "",
                rol="cliente",
                activo=True,
                estado_registro="aprobado",
                email_verificado=False,
                requiere_migracion_password=True,
            )
            fecha_alta = _fecha(datos.get("date_created_gmt") or datos.get("date_created"))
            if fecha_alta:
                usuario.creado_en = fecha_alta
                usuario.ultimo_acceso_en = fecha_alta
            db.add(usuario)
        else:
            if usuario.wordpress_id is None:
                usuario.wordpress_id = wordpress_id
            if usuario.origen == "web":
                usuario.origen = "web+wordpress"
            # Sólo una cuenta sin contraseña local necesita crearla. Una
            # actualización de migración no puede volver a bloquear a quien
            # ya terminó el cambio de clave en la nueva tienda.
            if (
                usuario.google_sub is None
                and usuario.rol != "admin"
                and usuario.password_hash is None
            ):
                usuario.requiere_migracion_password = True
            if usuario.rol != "admin" and nombre_wordpress and _debe_completar_nombre(usuario):
                usuario.nombre = nombre_wordpress
            if usuario.rol != "admin" and apellido_wordpress and not (usuario.apellido or "").strip():
                usuario.apellido = apellido_wordpress

        usuario.telefono = usuario.telefono or _texto(facturacion.get("phone"))
        usuario.provincia = usuario.provincia or _texto(facturacion.get("state"))
        usuario.localidad_partido = usuario.localidad_partido or _texto(facturacion.get("city"))
        direccion = " ".join(filter(None, [_texto(facturacion.get("address_1")), _texto(facturacion.get("address_2"))]))
        usuario.domicilio = usuario.domicilio or direccion or None
        db.flush()
        enlace = db.scalar(select(UsuarioWordpress).where(UsuarioWordpress.wordpress_id == wordpress_id))
        if enlace is None:
            db.add(UsuarioWordpress(wordpress_id=wordpress_id, usuario_id=usuario.id, email_original=email))
        else:
            enlace.usuario_id = usuario.id
            enlace.email_original = email
        resultado["creados" if creado else "vinculados"] += 1
        resultado["procesados"] += 1
        if resultado["procesados"] % 500 == 0:
            db.flush()
            if progreso:
                progreso(resultado.copy())
    db.commit()
    return resultado
