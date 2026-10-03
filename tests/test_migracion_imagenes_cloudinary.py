from sqlalchemy import select

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
