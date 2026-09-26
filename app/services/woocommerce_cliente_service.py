import secrets

from sqlalchemy.orm import Session

from app.core.security import hashear_password
from app.integrations.woocommerce import WooCommerceClient
from app.models.usuario import Usuario
from app.repositories.usuario_repository import get_usuario_by_email


def importar_cliente_woocommerce(db: Session, email: str) -> tuple[Usuario, bool, str | None]:
    email = email.strip().lower()
    data = WooCommerceClient().buscar_cliente_por_email(email)
    if data is None:
        raise ValueError("No se encontró el cliente en WooCommerce.")

    billing = data.get("billing") or {}
    shipping = data.get("shipping") or {}
    usuario = get_usuario_by_email(db, email)
    creado = usuario is None
    password_temporal = None
    if creado:
        password_temporal = secrets.token_urlsafe(16)
        usuario = Usuario(email=email, nombre="", rol="cliente")
        usuario.password_hash = hashear_password(password_temporal)
        db.add(usuario)

    nombre = (data.get("first_name") or billing.get("first_name") or data.get("username") or email.split("@", 1)[0]).strip()
    apellido = (data.get("last_name") or billing.get("last_name") or "").strip()
    direccion = billing.get("address_1") or shipping.get("address_1") or None
    complemento = billing.get("address_2") or shipping.get("address_2") or None
    usuario.nombre = nombre
    usuario.apellido = apellido
    usuario.telefono = billing.get("phone") or usuario.telefono
    usuario.domicilio = ", ".join(filter(None, (direccion, complemento))) or usuario.domicilio
    usuario.localidad_partido = billing.get("city") or shipping.get("city") or usuario.localidad_partido
    usuario.provincia = billing.get("state") or shipping.get("state") or usuario.provincia
    usuario.estado_registro = "aprobado"
    usuario.email_verificado = True
    usuario.activo = True
    db.commit()
    db.refresh(usuario)
    return usuario, creado, password_temporal
