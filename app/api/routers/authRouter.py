from datetime import datetime, timedelta, timezone
import hashlib
import secrets
import httpx
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.core.security import crear_token,hashear_password,require_cliente,verificar_password
from app.database.session import get_db
from app.models.usuario import Usuario
from app.models.notificacion import Notificacion
from app.repositories.usuario_repository import get_usuario_by_email
from app.schemas.auth_schemas import ActualizarPerfilRequest,AuthResponse,CambiarPasswordRequest,CompletarMigracionPasswordRequest,EstadoEmailResponse,LoginRequest,RegistroRequest,RegistroResponse,RestablecerPasswordRequest,SolicitarResetPasswordRequest,UsuarioResponse
from app.core.config import settings
from app.services.notificacion_service import notificar
from app.services.password_reset_email_service import construir_email_restablecimiento

router=APIRouter(prefix="/api/auth",tags=["Autenticación"])
RESET_RESPONSE={"mensaje":"Si el email corresponde a una cuenta, recibirás un enlace para cambiar la contraseña."}
REENVIO_RESET_MINUTOS = 2

def _es_cuenta_wordpress(usuario: Usuario | None, db: Session | None = None) -> bool:
    return bool(usuario and usuario.activo and usuario.requiere_migracion_password)


def _fecha_en_utc(fecha: datetime) -> datetime:
    """Normaliza fechas de PostgreSQL sin perder el huso horario almacenado."""
    if fecha.tzinfo is None:
        return fecha.replace(tzinfo=timezone.utc)
    return fecha.astimezone(timezone.utc)


def _enviar_enlace_restablecimiento(usuario: Usuario, db: Session, *, forzar: bool = False) -> bool:
    """Genera y envía un enlace, evitando duplicados por eventos del formulario."""
    ahora = datetime.now(timezone.utc)
    expira = usuario.reset_password_expira_en
    enlace_reciente = (
        usuario.reset_password_token_hash is not None
        and expira is not None
        and _fecha_en_utc(expira) > ahora + timedelta(hours=1, minutes=-REENVIO_RESET_MINUTOS)
    )
    if enlace_reciente and not forzar:
        return False

    token = secrets.token_urlsafe(48)
    usuario.reset_password_token_hash = hashlib.sha256(token.encode()).hexdigest()
    usuario.reset_password_expira_en = ahora + timedelta(hours=1)
    if not settings.RESEND_API_KEY:
        raise HTTPException(status_code=503, detail="El envío de emails no está configurado.")
    enlace = f"{settings.FRONTEND_URL.rstrip('/')}/restablecer-clave?token={token}"
    texto_email, html_email = construir_email_restablecimiento(
        nombre=usuario.nombre,
        enlace=enlace,
        logo_url=f"{settings.FRONTEND_URL.rstrip('/')}/brand/logo-pupas.jpg",
    )
    try:
        httpx.post("https://api.resend.com/emails",headers={"Authorization":f"Bearer {settings.RESEND_API_KEY}"},json={"from":settings.EMAIL_FROM,"to":[usuario.email],"subject":"Creá tu nueva contraseña de Pupas","text":texto_email,"html":html_email},timeout=15).raise_for_status()
    except httpx.HTTPError as error:
        db.rollback()
        raise HTTPException(status_code=502, detail="Resend rechazó el envío del email. Verificá EMAIL_FROM y el dominio en Resend.") from error
    db.commit()
    return True

@router.post("/solicitar-reset-password")
def solicitar_reset_password(data:SolicitarResetPasswordRequest,db:Session=Depends(get_db)):
    usuario=get_usuario_by_email(db,data.email.strip().lower())
    if usuario and usuario.activo:
        _enviar_enlace_restablecimiento(usuario, db)
    return RESET_RESPONSE

@router.post("/restablecer-password")
def restablecer_password(data:RestablecerPasswordRequest,db:Session=Depends(get_db)):
    usuario=db.scalar(select(Usuario).where(Usuario.reset_password_token_hash==hashlib.sha256(data.token.encode()).hexdigest()))
    expira=usuario.reset_password_expira_en if usuario else None
    if usuario is None or expira is None or _fecha_en_utc(expira)<datetime.now(timezone.utc):
        raise HTTPException(status_code=400,detail="El enlace es inválido o venció.")
    usuario.password_hash=hashear_password(data.password)
    usuario.requiere_migracion_password=False
    usuario.email_verificado=True
    usuario.reset_password_token_hash=None;usuario.reset_password_expira_en=None
    db.commit()
    return {"mensaje":"Contraseña actualizada correctamente."}
@router.post("/registro",response_model=RegistroResponse,status_code=201)
def registrar(data:RegistroRequest,db:Session=Depends(get_db)):
    email=data.email.strip().lower()
    if get_usuario_by_email(db,email):raise HTTPException(status_code=409,detail="Ya existe una cuenta con ese email.")
    usuario=Usuario(
        email=email,
        nombre=data.nombre.strip(),
        apellido=data.apellido.strip(),
        telefono=data.telefono.strip(),
        provincia=data.provincia.strip(),
        localidad_partido=data.localidad_partido.strip(),
        domicilio=data.domicilio.strip(),
        canal_venta=data.canal_venta,
        tienda_online_url=data.tienda_online_url.strip() if data.tienda_online_url else None,
        password_hash=hashear_password(data.password),
        rol="cliente",
        email_verificado=False,
        estado_registro="pendiente",
    )
    db.add(usuario);db.commit();db.refresh(usuario)
    return {"mensaje":"Registro recibido. Un administrador debe aprobar tu cuenta.","estado":"pendiente"}
@router.post("/login",response_model=AuthResponse)
def login(data:LoginRequest,db:Session=Depends(get_db)):
    usuario=get_usuario_by_email(db,data.email.strip().lower())
    if _es_cuenta_wordpress(usuario, db):
        raise HTTPException(status_code=409,detail="MIGRACION_PASSWORD_REQUERIDA")
    if usuario is None or usuario.password_hash is None or not verificar_password(data.password,usuario.password_hash):raise HTTPException(status_code=401,detail="Email o contraseña incorrectos.")
    if not usuario.activo:raise HTTPException(status_code=403,detail="La cuenta está deshabilitada.")
    if usuario.rol != "admin" and usuario.estado_registro != "aprobado":
        detalle = "Tu registro está pendiente de aprobación." if usuario.estado_registro == "pendiente" else "Tu registro fue rechazado. Contactate con la empresa."
        raise HTTPException(status_code=403,detail=detalle)
    if usuario.rol == "cliente" and not db.scalar(
        select(Notificacion.id).where(
            Notificacion.usuario_id == usuario.id,
            Notificacion.tipo == "bienvenida",
        )
    ):
        notificar(
            db,
            audiencia="cliente",
            tipo="bienvenida",
            titulo=f"¡Bienvenido/a, {usuario.nombre}!",
            mensaje=(
                "Este es tu sector de notificaciones. Acá vas a recibir novedades y ofertas, "
                "además de información importante sobre los productos incluidos en tus compras "
                "y las actualizaciones de tus pedidos."
            ),
            usuario_id=usuario.id,
        )
    usuario.ultimo_acceso_en=datetime.now(timezone.utc);db.commit()
    return {"access_token":crear_token(usuario),"usuario":usuario}

@router.post("/estado-email", response_model=EstadoEmailResponse)
def estado_email(data: SolicitarResetPasswordRequest, db: Session = Depends(get_db)):
    usuario = get_usuario_by_email(db, data.email.strip().lower())
    requiere_migracion = _es_cuenta_wordpress(usuario, db)
    # Este endpoint sólo identifica la cuenta. La interfaz solicita luego el
    # enlace una única vez; enviarlo aquí y de nuevo desde la interfaz agotaba
    # innecesariamente la cuota diaria de Resend.
    return {"requiere_migracion": requiere_migracion}

@router.post("/completar-migracion-password",response_model=AuthResponse)
def completar_migracion_password(data:CompletarMigracionPasswordRequest,db:Session=Depends(get_db)):
    usuario=get_usuario_by_email(db,data.email.strip().lower())
    if not _es_cuenta_wordpress(usuario, db):
        raise HTTPException(status_code=400,detail="La cuenta no requiere migración.")
    if not settings.WORDPRESS_MIGRATION_SECRET:
        raise HTTPException(status_code=503,detail="La validación de cuentas migradas no está configurada.")
    try:
        response=httpx.post(f"{settings.wordpress_source_url}/wp-json/pupas-migration/v1/verify",headers={"X-Pupas-Migration-Secret":settings.WORDPRESS_MIGRATION_SECRET},json={"email":usuario.email,"password":data.password_anterior},timeout=15)
    except httpx.HTTPError as error:
        raise HTTPException(status_code=502,detail="No se pudo validar la cuenta anterior.") from error
    if response.status_code != 200:
        raise HTTPException(status_code=401,detail="La contraseña anterior es incorrecta.")
    usuario.password_hash=hashear_password(data.password_nueva)
    usuario.requiere_migracion_password=False
    usuario.email_verificado=True
    db.commit();db.refresh(usuario)
    return {"access_token":crear_token(usuario),"usuario":usuario}
@router.get("/me",response_model=UsuarioResponse)
def me(usuario:Usuario=Depends(require_cliente)):return usuario

@router.patch("/me",response_model=UsuarioResponse)
def actualizar_perfil(data:ActualizarPerfilRequest,db:Session=Depends(get_db),usuario:Usuario=Depends(require_cliente)):
    documento=data.documento.strip() if data.documento else None
    if documento and db.scalar(select(Usuario).where(Usuario.documento==documento,Usuario.id!=usuario.id)):
        raise HTTPException(status_code=409,detail="Ese DNI o CUIT ya pertenece a otra cuenta.")
    usuario.nombre=data.nombre.strip();usuario.telefono=data.telefono.strip();usuario.documento=documento
    usuario.acepta_promociones_email=data.acepta_promociones_email
    usuario.provincia=data.provincia.strip() if data.provincia else None
    usuario.localidad_partido=data.localidad_partido.strip() if data.localidad_partido else None
    usuario.domicilio=data.domicilio.strip() if data.domicilio else None
    usuario.canal_venta=data.canal_venta
    usuario.tienda_online_url=data.tienda_online_url.strip() if data.tienda_online_url else None
    db.commit();db.refresh(usuario);return usuario

@router.patch("/me/password")
def cambiar_password(data:CambiarPasswordRequest,db:Session=Depends(get_db),usuario:Usuario=Depends(require_cliente)):
    if usuario.password_hash is None or not verificar_password(data.password_actual,usuario.password_hash):
        raise HTTPException(status_code=400,detail="La contraseña actual es incorrecta.")
    usuario.password_hash=hashear_password(data.password_nueva)
    db.commit()
    return {"mensaje":"Contraseña actualizada correctamente."}
