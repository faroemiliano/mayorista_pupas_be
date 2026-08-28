from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator


class GoogleLoginRequest(BaseModel):
    credential: str = Field(min_length=100)


class UsuarioResponse(BaseModel):
    id: int
    email: str
    nombre: str
    apellido: str
    telefono: str | None
    documento: str | None
    avatar_url: str | None
    rol: str
    email_verificado: bool
    estado_registro: str
    creado_en: datetime

    model_config = ConfigDict(from_attributes=True)


class RegistroRequest(BaseModel):
    nombre: str = Field(min_length=2, max_length=100)
    email: str = Field(pattern=r"^[^\s@]+@[^\s@]+\.[^\s@]+$", max_length=255)
    telefono: str = Field(min_length=6, max_length=50)
    documento: str | None = Field(default=None, pattern=r"^\d{7,11}$")
    password: str = Field(min_length=8, max_length=128)
    confirmar_password: str = Field(min_length=8, max_length=128)

    @model_validator(mode="after")
    def validar_passwords(self):
        if self.password != self.confirmar_password:
            raise ValueError("Las contraseñas no coinciden.")
        return self


class LoginRequest(BaseModel):
    email: str = Field(pattern=r"^[^\s@]+@[^\s@]+\.[^\s@]+$", max_length=255)
    password: str


class ActualizarPerfilRequest(BaseModel):
    nombre: str = Field(min_length=2, max_length=100)
    telefono: str = Field(min_length=6, max_length=50)
    documento: str | None = Field(default=None, pattern=r"^\d{7,11}$")


class AuthResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    usuario: UsuarioResponse


class RegistroResponse(BaseModel):
    mensaje: str
    estado: str
