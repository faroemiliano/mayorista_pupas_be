import httpx
import time

from app.core.config import settings


class WooCommerceClient:
    def __init__(self) -> None:
        if not all((settings.WOOCOMMERCE_URL, settings.WOOCOMMERCE_CONSUMER_KEY, settings.WOOCOMMERCE_CONSUMER_SECRET)):
            raise RuntimeError("Faltan las credenciales de WooCommerce.")
        self.base_url = settings.wordpress_source_url

    def buscar_cliente_por_email(self, email: str) -> dict | None:
        response = httpx.get(
            f"{self.base_url}/wp-json/wc/v3/customers",
            params={"email": email.strip().lower(), "per_page": 1},
            auth=(settings.WOOCOMMERCE_CONSUMER_KEY, settings.WOOCOMMERCE_CONSUMER_SECRET),
            timeout=30,
        )
        response.raise_for_status()
        clientes = response.json()
        return clientes[0] if clientes else None

    def _get(self, endpoint: str, params: dict | None = None):
        return self._get_response(endpoint, params).json()

    def _get_response(self, endpoint: str, params: dict | None = None) -> httpx.Response:
        ultimo_error: Exception | None = None
        for intento in range(4):
            try:
                response = httpx.get(
                    f"{self.base_url}/wp-json/wc/v3/{endpoint.lstrip('/')}",
                    params=params,
                    auth=(settings.WOOCOMMERCE_CONSUMER_KEY, settings.WOOCOMMERCE_CONSUMER_SECRET),
                    timeout=60,
                )
                response.raise_for_status()
                return response
            except (httpx.HTTPError, httpx.TimeoutException) as error:
                ultimo_error = error
                if intento < 3:
                    time.sleep(2 ** intento)
        raise RuntimeError(f"WooCommerce no respondió después de varios intentos: {endpoint}") from ultimo_error

    def obtener_pagina(self, recurso: str, pagina: int, por_pagina: int = 100) -> tuple[list[dict], int]:
        response = self._get_response(recurso, {
            "page": pagina,
            "per_page": por_pagina,
            "orderby": "id",
            "order": "asc",
        })
        return response.json(), int(response.headers.get("X-WP-TotalPages", "1"))

    def obtener_total(self, recurso: str, params: dict | None = None) -> int:
        response = self._get_response(recurso, {"page": 1, "per_page": 1, **(params or {})})
        return int(response.headers.get("X-WP-Total", "0"))

    def _get_wordpress_response(self, recurso: str, params: dict | None = None) -> httpx.Response:
        response = httpx.get(
            f"{self.base_url}/wp-json/wp/v2/{recurso.lstrip('/')}",
            params=params,
            timeout=60,
        )
        response.raise_for_status()
        return response

    def obtener_pagina_wordpress(
        self, recurso: str, pagina: int, por_pagina: int = 100,
    ) -> tuple[list[dict], int]:
        response = self._get_wordpress_response(recurso, {
            "page": pagina,
            "per_page": por_pagina,
            "orderby": "id",
            "order": "asc",
        })
        return response.json(), int(response.headers.get("X-WP-TotalPages", "1"))

    def obtener_producto(self, producto_id: int) -> dict:
        producto = self._get(f"products/{producto_id}")
        producto["_variaciones_completas"] = self._get(
            f"products/{producto_id}/variations", {"per_page": 100}
        )
        return producto

    def obtener_pedido(self, pedido_id: int) -> dict:
        return self._get(f"orders/{pedido_id}")

    def obtener_variaciones(self, producto_id: int) -> list[dict]:
        variaciones: list[dict] = []
        pagina = 1
        paginas = 1
        while pagina <= paginas:
            lote, paginas = self.obtener_pagina(f"products/{producto_id}/variations", pagina)
            variaciones.extend(lote)
            pagina += 1
        return variaciones
