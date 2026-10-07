from sqlalchemy import select
from cloudinary.exceptions import Error as CloudinaryError

from app.core.config import settings
from app.models.imagen_producto import ImagenProducto
from app.models.producto import Producto
from app.services.migracion_imagenes_cloudinary_service import migrar_imagenes_a_cloudinary


def test_migra_imagen_wordpress_a_cloudinary(db, monkeypatch):
    url_wordpress = "https://wordpress.test/wp-content/uploads/2026/10/foto.jpg"
    url_cloudinary = "https://res.cloudinary.com/demo/image/upload/v1/pupas/foto.jpg"
    producto = Producto(
        dux_codigo="WP-CLOUD-1", nombre="Producto con foto", slug="producto-cloud",
        origen="wordpress", imagen_url=url_wordpress,
    )
    producto.imagenes.append(ImagenProducto(url=url_wordpress, orden=0, principal=True))
    db.add(producto)
    db.commit()
    monkeypatch.setattr(settings, "WOOCOMMERCE_URL", "https://wordpress.test")
    monkeypatch.setattr(settings, "CLOUDINARY_URL", "cloudinary://key:secret@demo")
    monkeypatch.setattr(
        "app.services.migracion_imagenes_cloudinary_service._subir_imagen",
        lambda _imagen: url_cloudinary,
    )

    resultado = migrar_imagenes_a_cloudinary(db)

    imagen = db.scalar(select(ImagenProducto))
    db.refresh(producto)
    assert resultado["copiadas"] == 1
    assert imagen.url == url_cloudinary
    assert producto.imagen_url == url_cloudinary


def test_migracion_de_prueba_limita_y_conserva_origen(db, monkeypatch):
    monkeypatch.setattr(settings, "WOOCOMMERCE_URL", "https://wordpress.test")
    monkeypatch.setattr(settings, "CLOUDINARY_URL", "cloudinary://key:secret@demo")
    for numero in range(3):
        url = f"https://wordpress.test/wp-content/uploads/2026/10/foto-{numero}.jpg"
        producto = Producto(
            dux_codigo=f"WP-CLOUD-LIM-{numero}", nombre=f"Producto {numero}",
            slug=f"producto-{numero}", origen="wordpress", imagen_url=url,
        )
        producto.imagenes.append(ImagenProducto(url=url, orden=0, principal=True))
        db.add(producto)
    db.commit()
    monkeypatch.setattr(
        "app.services.migracion_imagenes_cloudinary_service._subir_imagen",
        lambda imagen: f"https://res.cloudinary.com/demo/image/upload/v1/pupas/{imagen.id}.jpg",
    )

    resultado = migrar_imagenes_a_cloudinary(db, limite=2)

    imagenes = db.scalars(select(ImagenProducto).order_by(ImagenProducto.id)).all()
    assert resultado["copiadas"] == 2
    assert resultado["pendientes_para_reintentar"] == 1
    assert resultado["prueba"] is True
    assert sum(imagen.url.startswith("https://res.cloudinary.com/") for imagen in imagenes) == 2
    assert all(imagen.origen_url for imagen in imagenes[:2])


def test_migracion_reintenta_subiendo_bytes_si_cloudinary_no_lee_la_url(db, monkeypatch):
    url_wordpress = "https://wordpress.test/wp-content/uploads/2026/10/bloqueada.jpg"
    url_cloudinary = "https://res.cloudinary.com/demo/image/upload/v1/pupas/bloqueada.jpg"
    producto = Producto(
        dux_codigo="WP-CLOUD-FALLBACK", nombre="Imagen bloqueada",
        slug="imagen-bloqueada", origen="wordpress", imagen_url=url_wordpress,
    )
    producto.imagenes.append(ImagenProducto(url=url_wordpress, orden=0, principal=True))
    db.add(producto)
    db.commit()
    monkeypatch.setattr(settings, "WOOCOMMERCE_URL", "https://wordpress.test")
    monkeypatch.setattr(settings, "CLOUDINARY_URL", "cloudinary://key:secret@demo")
    llamadas = []

    def upload(origen, **_opciones):
        llamadas.append(origen)
        if isinstance(origen, str):
            raise CloudinaryError("El host no permite descarga remota")
        return {"secure_url": url_cloudinary}

    class Respuesta:
        content = b"\xff\xd8\xffimagen"

        @staticmethod
        def raise_for_status():
            return None

    monkeypatch.setattr(
        "app.services.migracion_imagenes_cloudinary_service.cloudinary.uploader.upload",
        upload,
    )
    monkeypatch.setattr(
        "app.services.migracion_imagenes_cloudinary_service.httpx.get",
        lambda *_args, **_kwargs: Respuesta(),
    )

    resultado = migrar_imagenes_a_cloudinary(db, limite=1)

    assert resultado["copiadas"] == 1
    assert len(llamadas) == 2
    assert isinstance(llamadas[0], str)
    assert not isinstance(llamadas[1], str)
