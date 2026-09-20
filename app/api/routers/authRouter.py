from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.core.security import crear_token,hashear_password,require_cliente,verificar_password
from app.database.session import get_db
from app.models.usuario import Usuario
from app.models.notificacion import Notificacion
from app.repositories.usuario_repository import get_usuario_by_email
from app.schemas.auth_schemas import ActualizarPerfilRequest,AuthResponse,CambiarPasswordRequest,LoginRequest,RegistroRequest,RegistroResponse,UsuarioResponse
from app.services.notificacion_service import notificar

router=APIRouter(prefix="/api/auth",tags=["Autenticación"])
@router.post("/registro",response_model=RegistroResponse,status_code=201)
def registrar(data:RegistroRequest,db:Session=Depends(get_db)):
    email=data.email.strip().lower()
    if get_usuario_by_email(db,email):raise HTTPException(status_code=409,detail="Ya existe una cuenta con ese email.")
    usuario=Usuario(
        email=email,
        nombre=data.nombre.strip(),
        apellido="",
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
