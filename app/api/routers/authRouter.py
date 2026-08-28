from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.core.security import crear_token,hashear_password,require_cliente,verificar_password
from app.database.session import get_db
from app.models.usuario import Usuario
from app.repositories.usuario_repository import get_usuario_by_email
from app.schemas.auth_schemas import ActualizarPerfilRequest,AuthResponse,LoginRequest,RegistroRequest,RegistroResponse,UsuarioResponse

router=APIRouter(prefix="/api/auth",tags=["Autenticación"])
@router.post("/registro",response_model=RegistroResponse,status_code=201)
def registrar(data:RegistroRequest,db:Session=Depends(get_db)):
    email=data.email.strip().lower()
    if get_usuario_by_email(db,email):raise HTTPException(status_code=409,detail="Ya existe una cuenta con ese email.")
    documento = data.documento.strip() if data.documento else None
    if documento and db.scalar(select(Usuario).where(Usuario.documento == documento)):
        raise HTTPException(status_code=409,detail="Ya existe una cuenta con ese DNI o CUIT.")
    usuario=Usuario(email=email,nombre=data.nombre.strip(),apellido="",telefono=data.telefono.strip(),documento=documento,password_hash=hashear_password(data.password),rol="cliente",email_verificado=False,estado_registro="pendiente")
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
    db.commit();db.refresh(usuario);return usuario
