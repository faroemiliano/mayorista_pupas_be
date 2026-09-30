import base64
import binascii
import threading
import time
from urllib.parse import urlsplit

import httpx

from app.core.config import settings


class DuxClient:
    BASE_URL = (
        "https://erp.duxsoftware.com.ar/"
        "WSERP/rest/services"
    )
    IMAGE_HOST = "erp.duxsoftware.com.ar"
    IMAGE_PATH = "/servicioimagenes/images/"
    MIN_REQUEST_INTERVAL_SECONDS = 5.0
    _rate_limit_lock = threading.Lock()
    _last_request_started_at = 0.0

    def __init__(self) -> None:
        self.token = settings.DUX_API_TOKEN
        self.id_empresa = settings.DUX_ID_EMPRESA

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.token}",
            "Accept": "application/json",
        }

    @classmethod
    def _wait_for_rate_limit(cls) -> None:
        """Serializa inicios de requests para respetar el límite público Dux."""

        with cls._rate_limit_lock:
            elapsed = time.monotonic() - cls._last_request_started_at
            remaining = cls.MIN_REQUEST_INTERVAL_SECONDS - elapsed
            if remaining > 0:
                time.sleep(remaining)
            cls._last_request_started_at = time.monotonic()

    def get(
        self,
        endpoint: str,
        params: dict | None = None,
        reintentos: int = 3,
    ):
        url = (
            f"{self.BASE_URL}/"
            f"{endpoint.lstrip('/')}"
        )

        ultimo_error = None

        for intento in range(
            1,
            reintentos + 1,
        ):
            try:
                self._wait_for_rate_limit()
                response = httpx.get(
                    url,
                    headers=self._headers(),
                    params=params,
                    timeout=30.0,
                )

                response.raise_for_status()

                return response.json()

            except httpx.HTTPStatusError as error:
                ultimo_error = error

                status = error.response.status_code

                print(
                    f"⚠️ Dux respondió {status} "
                    f"(intento {intento}/{reintentos})"
                )

                # Reintentamos solamente errores temporales o de rate limit.
                if (
                    status in {429, 500, 502, 503, 504}
                    and intento < reintentos
                ):
                    retry_after = error.response.headers.get("Retry-After")
                    try:
                        espera = float(retry_after) if retry_after else 5.0 * intento
                    except ValueError:
                        espera = 5.0 * intento
                    time.sleep(max(espera, self.MIN_REQUEST_INTERVAL_SECONDS))
                    continue

                print(
                    "Respuesta Dux:",
                    error.response.text[:1000],
                )

                raise

            except httpx.RequestError as error:
                ultimo_error = error

                print(
                    f"⚠️ Error de conexión con Dux "
                    f"(intento {intento}/{reintentos})"
                )

                if intento < reintentos:
                    time.sleep(2 * intento)
                    continue

                raise

        raise ultimo_error

    def post(self, endpoint: str, json: dict, params: dict | None = None):
        if not settings.DUX_ESCRITURA_HABILITADA:
            raise RuntimeError("La escritura en Dux está deshabilitada por configuración.")
        url = f"{self.BASE_URL}/{endpoint.lstrip('/')}"
        self._wait_for_rate_limit()
        response = httpx.post(url, headers=self._headers(), params=params, json=json, timeout=30.0)
        response.raise_for_status()
        return response.json()

    def get_imagen(
        self,
        url: str,
    ) -> tuple[bytes, str]:

        parsed_url = urlsplit(url)

        if (
            parsed_url.scheme != "https"
            or parsed_url.hostname != self.IMAGE_HOST
            or parsed_url.path != self.IMAGE_PATH
        ):
            raise ValueError(
                "URL de imagen Dux no permitida."
            )

        response = httpx.get(
            url,
            headers=self._headers(),
            timeout=30.0,
        )
        response.raise_for_status()

        try:
            imagen = base64.b64decode(
                response.content,
                validate=True,
            )
        except (binascii.Error, ValueError) as error:
            raise ValueError(
                "Dux devolvió una imagen inválida."
            ) from error

        if imagen.startswith(b"\xff\xd8\xff"):
            media_type = "image/jpeg"
        elif imagen.startswith(b"\x89PNG\r\n\x1a\n"):
            media_type = "image/png"
        elif imagen.startswith((b"GIF87a", b"GIF89a")):
            media_type = "image/gif"
        elif (
            imagen.startswith(b"RIFF")
            and imagen[8:12] == b"WEBP"
        ):
            media_type = "image/webp"
        else:
            raise ValueError(
                "Formato de imagen Dux no soportado."
            )

        return imagen, media_type
