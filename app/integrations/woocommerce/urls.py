from urllib.parse import urlsplit, urlunsplit

from app.core.config import settings


def es_url_wordpress(url: str) -> bool:
    parsed = urlsplit(url)
    hosts = {
        urlsplit(valor).hostname
        for valor in (settings.WOOCOMMERCE_URL, settings.wordpress_source_url)
        if valor
    }
    return parsed.scheme == "https" and parsed.hostname in hosts


def url_desde_origen_wordpress(url: str) -> str:
    """Conserva la ruta del medio y la sirve desde el host técnico anterior."""
    parsed = urlsplit(url)
    if not es_url_wordpress(url) or not settings.WORDPRESS_ORIGIN_URL:
        return url
    origen = urlsplit(settings.wordpress_source_url)
    return urlunsplit((origen.scheme, origen.netloc, parsed.path, parsed.query, parsed.fragment))
