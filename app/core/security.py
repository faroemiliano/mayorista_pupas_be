from datetime import datetime, timedelta, timezone
import jwt
from jwt.exceptions import InvalidTokenError
from pwdlib import PasswordHash
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session
from app.core.config import settings
from app.database.session import get_db
from app.models.usuario import Usuario
from app.repositories.usuario_repository import get_usuario_by_id

bearer=HTTPBearer(auto_error=False)
password_hash=PasswordHash.recommended()
def crear_token(usuario:Usuario)->str:
    exp=datetime.now(timezone.utc)+timedelta(minutes=settings.AUTH_TOKEN_MINUTES)
    return jwt.encode({"sub":str(usuario.id),"exp":exp},settings.AUTH_SECRET_KEY,algorithm="HS256")
def hashear_password(password:str)->str:return password_hash.hash(password)
def verificar_password(password:str,hashed:str)->bool:return password_hash.verify(password,hashed)
def get_usuario_opcional(credentials:HTTPAuthorizationCredentials|None=Depends(bearer),db:Session=Depends(get_db))->Usuario|None:
    if credentials is None:return None
    try: usuario_id=int(jwt.decode(credentials.credentials,settings.AUTH_SECRET_KEY,algorithms=["HS256"])["sub"])
    except (InvalidTokenError,KeyError,ValueError) as error: raise HTTPException(status_code=401,detail="Sesión inválida o vencida.") from error
    usuario=get_usuario_by_id(db,usuario_id)
    if usuario is None or not usuario.activo:raise HTTPException(status_code=401,detail="Usuario no habilitado.")
    return usuario
def require_cliente(usuario:Usuario|None=Depends(get_usuario_opcional))->Usuario:
    if usuario is None:raise HTTPException(status_code=401,detail="Tenés que iniciar sesión.")
    return usuario
def require_admin(usuario:Usuario=Depends(require_cliente))->Usuario:
    if usuario.rol!="admin":raise HTTPException(status_code=403,detail="Se requiere permiso de administrador.")
    return usuario
