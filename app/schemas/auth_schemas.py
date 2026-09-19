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
    provincia: str | None
    localidad_partido: str | None
    domicilio: str | None
    canal_venta: str | None
    tienda_online_url: str | None
    avatar_url: str | None
    rol: str
    email_verificado: bool
    acepta_promociones_email: bool
    estado_registro: str
    dux_id_cliente: int | None
    creado_en: datetime

    model_config = ConfigDict(from_attributes=True)


class RegistroRequest(BaseModel):
    nombre: str = Field(min_length=2, max_length=100)
    email: str = Field(pattern=r"^[^\s@]+@[^\s@]+\.[^\s@]+$", max_length=255)
    telefono: str = Field(min_length=6, max_length=50)
    provincia: str = Field(min_length=2, max_length=100)
    localidad_partido: str = Field(min_length=2, max_length=150)
    domicilio: str = Field(min_length=4, max_length=250)
    canal_venta: str = Field(pattern=r"^(local_fisico|tienda_online|ambos)$")
    tienda_online_url: str | None = Field(default=None, max_length=500)
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
    acepta_promociones_email: bool = False
    provincia: str | None = Field(default=None, max_length=100)
    localidad_partido: str | None = Field(default=None, max_length=150)
    domicilio: str | None = Field(default=None, max_length=250)
    canal_venta: str | None = Field(default=None, pattern=r"^(local_fisico|tienda_online|ambos)$")
    tienda_online_url: str | None = Field(default=None, max_length=500)


class AuthResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    usuario: UsuarioResponse


class RegistroResponse(BaseModel):
    mensaje: str
    estado: str
