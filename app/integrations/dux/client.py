import time

import httpx

from app.core.config import settings


class DuxClient:
    BASE_URL = (
        "https://erp.duxsoftware.com.ar/"
        "WSERP/rest/services"
    )

    def __init__(self) -> None:
        self.token = settings.DUX_API_TOKEN
        self.id_empresa = settings.DUX_ID_EMPRESA

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.token}",
            "Accept": "application/json",
        }

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

                # Reintentamos solamente errores
                # temporales del servidor.
                if (
                    status in {500, 502, 503, 504}
                    and intento < reintentos
                ):
                    time.sleep(2 * intento)
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