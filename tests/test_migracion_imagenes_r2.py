from sqlalchemy import select

from app.core.config import settings
from app.models.imagen_producto import ImagenProducto
from app.models.producto import Producto
from app.services import migracion_imagenes_r2_service as migracion_r2


def test_migra_todas_las_imagenes_de_un_producto_y_guarda_respaldo(db, monkeypatch):
    producto = Producto(
        dux_codigo="WEB-R2-PRUEBA",
        nombre="Pijama R2",
        slug="pijama-r2",
        imagen_url="https://res.cloudinary.com/demo/image/upload/pijama.jpg",
    )
    db.add(producto)
    db.flush()
    imagen = ImagenProducto(
        producto_id=producto.id,
        url="https://res.cloudinary.com/demo/image/upload/pijama.jpg",
        contenido=b"imagen-prueba",
        media_type="image/webp",
        principal=True,
    )
    db.add(imagen)
    db.commit()

    monkeypatch.setattr(settings, "R2_ACCOUNT_ID", "cuenta")
    monkeypatch.setattr(settings, "R2_ACCESS_KEY_ID", "key")
    monkeypatch.setattr(settings, "R2_SECRET_ACCESS_KEY", "secret")
    monkeypatch.setattr(settings, "R2_BUCKET_NAME", "pupas-product-images")
    monkeypatch.setattr(settings, "R2_PUBLIC_BASE_URL", "https://imagenes.pupasmayorista.com.ar")
    monkeypatch.setattr(
        migracion_r2,
        "subir_imagen_producto_a_r2",
        lambda **kwargs: f"https://imagenes.pupasmayorista.com.ar/pupas/{kwargs['imagen_id']}.webp",
    )

    resultado = migracion_r2.migrar_imagenes_producto_a_r2(db, producto.id)

    assert resultado["actualizado"] is True
    assert resultado["copiadas"] == 1
    db.expire_all()
    imagen_actualizada = db.scalar(select(ImagenProducto).where(ImagenProducto.id == imagen.id))
    producto_actualizado = db.get(Producto, producto.id)
    assert imagen_actualizada.respaldo_url == "https://res.cloudinary.com/demo/image/upload/pijama.jpg"
    assert imagen_actualizada.url == f"https://imagenes.pupasmayorista.com.ar/pupas/{imagen.id}.webp"
    assert producto_actualizado.imagen_url == imagen_actualizada.url
