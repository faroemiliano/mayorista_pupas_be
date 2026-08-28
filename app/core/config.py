from decimal import Decimal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    DATABASE_URL: str

    DUX_API_TOKEN: str
    DUX_ID_EMPRESA: int | None = None
    DUX_ID_SUCURSAL: int | None = None
    DUX_ID_DEPOSITO: int | None = None
    DUX_PERSONALES_PEDIDOS: str = "1051689,796900"
    DUX_ESCRITURA_HABILITADA: bool = False

    @property
    def dux_personales_pedidos(self) -> list[int]:
        return [int(value.strip()) for value in self.DUX_PERSONALES_PEDIDOS.split(",") if value.strip()]
    GOOGLE_CLIENT_ID: str = ""
    AUTH_SECRET_KEY: str = "cambiar-esta-clave-en-produccion-pupas-2026"
    AUTH_TOKEN_MINUTES: int = 10080

    DUX_LISTA_PRECIO_MAYORISTA_ID: int = 4710
    DUX_LISTA_PRECIO_24_ID: int = 43406
    COMPRA_MINIMA: Decimal = Decimal("100000.00")

    CORS_ORIGINS: str = (
        "http://localhost:3000,"
        "http://localhost:5173,"
        "http://127.0.0.1:3000,"
        "http://127.0.0.1:5173"
    )

    @property
    def cors_origins(self) -> list[str]:
        return [
            origin.strip().rstrip("/")
            for origin in self.CORS_ORIGINS.split(",")
            if origin.strip()
        ]

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
    )


settings = Settings()
