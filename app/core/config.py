from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    DATABASE_URL: str

    @field_validator("DATABASE_URL", mode="before")
    @classmethod
    def use_psycopg_driver(cls, value: str) -> str:
        """Use Psycopg 3 with provider URLs such as Render's connection string."""
        if isinstance(value, str) and value.startswith("postgresql://"):
            return value.replace("postgresql://", "postgresql+psycopg://", 1)
        return value

    @field_validator("DUX_ID_PERSONAL_PEDIDOS_WEB", mode="before")
    @classmethod
    def empty_personal_is_none(cls, value: str | int | None) -> str | int | None:
        return None if value is None or (isinstance(value, str) and not value.strip()) else value

    DUX_API_TOKEN: str
    DUX_ID_EMPRESA: int | None = None
    DUX_ID_SUCURSAL: int | None = None
    DUX_ID_DEPOSITO: int | None = None
    DUX_PERSONALES_PEDIDOS: str = "1051689,796900"
    DUX_ESCRITURA_HABILITADA: bool = False
    DUX_ENVIO_AUTOMATICO_PEDIDOS_HABILITADO: bool = False
    DUX_ID_PERSONAL_PEDIDOS_WEB: int | None = None
    DUX_SINCRONIZACION_HABILITADA: bool = False
    DUX_RECONCILIACION_RESERVA_MINUTOS: int = 10
    SMTP_HABILITADO: bool = False
    SMTP_HOST: str = ""
    SMTP_PORT: int = 587
    SMTP_USUARIO: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_REMITENTE: str = ""
    EMAIL_ADMIN: str = ""
    WHATSAPP_EMPRESA: str = ""
    WOOCOMMERCE_URL: str = ""
    # Host técnico del WordPress anterior. Permite seguir leyendo la API y
    # descargar medios aunque el dominio comercial ya apunte a Vercel.
    WORDPRESS_ORIGIN_URL: str = ""
    WOOCOMMERCE_CONSUMER_KEY: str = ""
    WOOCOMMERCE_CONSUMER_SECRET: str = ""
    FRONTEND_URL: str = "http://localhost:5173"
    RESEND_API_KEY: str = ""
    EMAIL_FROM: str = "Pupas Mayorista <onboarding@resend.dev>"
    WORDPRESS_MIGRATION_SECRET: str = ""
    # La migración terminó. Por seguridad, sus acciones manuales quedan
    # bloqueadas hasta que se habiliten explícitamente desde el código.
    MIGRACION_WORDPRESS_ACCIONES_HABILITADAS: bool = False
    CLOUDINARY_URL: str = ""
    # Almacenamiento propio de imágenes. Si estas variables no están
    # configuradas, las cargas nuevas continúan usando Cloudinary.
    R2_ACCOUNT_ID: str = ""
    R2_ACCESS_KEY_ID: str = ""
    R2_SECRET_ACCESS_KEY: str = ""
    R2_BUCKET_NAME: str = ""
    R2_ENDPOINT_URL: str = ""
    R2_PUBLIC_BASE_URL: str = ""
    # Google Analytics 4. Se configura únicamente en Render; el JSON de la
    # cuenta de servicio no se expone nunca al navegador.
    GA4_PROPERTY_ID: str = ""
    GA4_SERVICE_ACCOUNT_JSON: str = ""

    @field_validator("CLOUDINARY_URL")
    @classmethod
    def validar_cloudinary_url(cls, value: str) -> str:
        if not value:
            return value
        if not value.startswith("cloudinary://") or "@" not in value:
            raise ValueError("CLOUDINARY_URL debe tener el formato cloudinary://API_KEY:API_SECRET@CLOUD_NAME")
        return value

    @property
    def r2_imagenes_configurado(self) -> bool:
        return all((
            self.R2_ACCOUNT_ID,
            self.R2_ACCESS_KEY_ID,
            self.R2_SECRET_ACCESS_KEY,
            self.R2_BUCKET_NAME,
            self.R2_PUBLIC_BASE_URL,
        ))

    @property
    def r2_endpoint_url(self) -> str:
        if self.R2_ENDPOINT_URL.strip():
            return self.R2_ENDPOINT_URL.rstrip("/")
        return f"https://{self.R2_ACCOUNT_ID}.r2.cloudflarestorage.com"

    @property
    def ga4_analytics_configurado(self) -> bool:
        return bool(self.GA4_PROPERTY_ID.strip() and self.GA4_SERVICE_ACCOUNT_JSON.strip())

    @property
    def dux_personales_pedidos(self) -> list[int]:
        return [int(value.strip()) for value in self.DUX_PERSONALES_PEDIDOS.split(",") if value.strip()]

    @property
    def wordpress_source_url(self) -> str:
        return (self.WORDPRESS_ORIGIN_URL or self.WOOCOMMERCE_URL).rstrip("/")
    GOOGLE_CLIENT_ID: str = ""
    AUTH_SECRET_KEY: str = "cambiar-esta-clave-en-produccion-pupas-2026"
    AUTH_TOKEN_MINUTES: int = 10080

    DUX_LISTA_PRECIO_MAYORISTA_ID: int = 4710
    DUX_LISTA_PRECIO_24_ID: int = 43406
    CARRITO_RESERVA_MINUTOS: int = 30

    CORS_ORIGINS: str = (
        "http://localhost:3000,"
        "http://localhost:5173,"
        "http://127.0.0.1:3000,"
        "http://127.0.0.1:5173"
    )

    @property
    def cors_origins(self) -> list[str]:
        configurados = [
            origin.strip().rstrip("/")
            for origin in self.CORS_ORIGINS.split(",")
            if origin.strip()
        ]
        # Durante el cambio de dominio ambas interfaces pueden convivir.
        transicion = [
            "https://mayorista-pupas-fe.vercel.app",
            "https://pupasmayorista.com.ar",
            "https://www.pupasmayorista.com.ar",
        ]
        return list(dict.fromkeys([*configurados, *transicion]))

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
