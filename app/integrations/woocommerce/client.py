import httpx

from app.core.config import settings


class WooCommerceClient:
    def __init__(self) -> None:
        if not all((settings.WOOCOMMERCE_URL, settings.WOOCOMMERCE_CONSUMER_KEY, settings.WOOCOMMERCE_CONSUMER_SECRET)):
            raise RuntimeError("Faltan las credenciales de WooCommerce.")
        self.base_url = settings.WOOCOMMERCE_URL.rstrip("/")

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
        response = httpx.get(
            f"{self.base_url}/wp-json/wc/v3/{endpoint.lstrip('/')}",
            params=params,
            auth=(settings.WOOCOMMERCE_CONSUMER_KEY, settings.WOOCOMMERCE_CONSUMER_SECRET),
            timeout=30,
        )
        response.raise_for_status()
        return response.json()

    def obtener_producto(self, producto_id: int) -> dict:
        producto = self._get(f"products/{producto_id}")
        producto["_variaciones_completas"] = self._get(
            f"products/{producto_id}/variations", {"per_page": 100}
        )
        return producto

    def obtener_pedido(self, pedido_id: int) -> dict:
        return self._get(f"orders/{pedido_id}")
