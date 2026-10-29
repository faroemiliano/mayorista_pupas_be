from app.core.config import settings
from app.services import almacenamiento_imagenes_r2_service as r2


class _ClienteR2Falso:
    def __init__(self):
        self.cargas = []

    def put_object(self, **kwargs):
        self.cargas.append(kwargs)

    def head_object(self, **kwargs):
        return {"ContentLength": 6, "ContentType": "image/webp"}


def _configurar_r2(monkeypatch):
    monkeypatch.setattr(settings, "R2_ACCOUNT_ID", "cuenta-prueba")
    monkeypatch.setattr(settings, "R2_ACCESS_KEY_ID", "access-key")
    monkeypatch.setattr(settings, "R2_SECRET_ACCESS_KEY", "secret-key")
    monkeypatch.setattr(settings, "R2_BUCKET_NAME", "pupas-product-images")
    monkeypatch.setattr(settings, "R2_PUBLIC_BASE_URL", "https://imagenes.pupasmayorista.com.ar")


def test_subir_imagen_a_r2_usa_url_y_cache_publicos(monkeypatch):
    _configurar_r2(monkeypatch)
    cliente = _ClienteR2Falso()
    monkeypatch.setattr(r2, "_cliente_r2", lambda: cliente)
    monkeypatch.setattr(r2, "_verificar_imagen_publica_r2", lambda **_: None)

    url = r2.subir_imagen_producto_a_r2(
        contenido=b"imagen", producto_id=42, media_type="image/webp"
    )

    assert url.startswith("https://imagenes.pupasmayorista.com.ar/pupas/catalogo/productos/42/imagenes/")
    assert url.endswith(".webp")
    assert len(cliente.cargas) == 1
    assert cliente.cargas[0] == {
        "Bucket": "pupas-product-images",
        "Key": url.removeprefix("https://imagenes.pupasmayorista.com.ar/"),
        "Body": b"imagen",
        "ContentType": "image/webp",
        "CacheControl": "public, max-age=31536000, immutable",
    }


def test_carga_nueva_prefiere_r2_cuando_esta_configurado(monkeypatch):
    _configurar_r2(monkeypatch)
    monkeypatch.setattr(r2, "subir_imagen_producto_a_r2", lambda **_: "https://imagenes.pupasmayorista.com.ar/foto.jpg")

    url = r2.subir_imagen_producto(
        contenido=b"imagen", producto_id=1, imagen_id=2, nombre="foto.jpg", media_type="image/jpeg"
    )

    assert url == "https://imagenes.pupasmayorista.com.ar/foto.jpg"


def test_verificacion_publica_reintenta_una_respuesta_transitoria(monkeypatch):
    _configurar_r2(monkeypatch)
    cliente = _ClienteR2Falso()
    monkeypatch.setattr(r2, "_cliente_r2", lambda: cliente)
    respuestas = iter([
        type("Respuesta", (), {"status_code": 404, "headers": {}})(),
        type(
            "Respuesta",
            (),
            {"status_code": 200, "headers": {"content-type": "image/webp"}},
        )(),
    ])
    monkeypatch.setattr(r2.httpx, "head", lambda *_args, **_kwargs: next(respuestas))
    esperas = []
    monkeypatch.setattr(r2.time, "sleep", esperas.append)

    r2._verificar_imagen_publica_r2(clave="pupas/catalogo/productos/1/foto.webp")

    assert esperas == [0.5]
