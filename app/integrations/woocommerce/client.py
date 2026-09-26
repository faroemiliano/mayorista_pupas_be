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
