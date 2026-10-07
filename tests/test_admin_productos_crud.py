import base64

from sqlalchemy import select

from app.models.categoria import Categoria
from app.models.imagen_producto import ImagenProducto
from app.models.producto import Producto


def test_admin_crea_edita_y_carga_imagen_de_producto(client, db, monkeypatch):
    url_cloudinary = "https://res.cloudinary.com/demo/image/upload/v1/pupas/producto.png"
    monkeypatch.setattr(
        "app.api.routers.adminProductosRouter.subir_imagen_producto_a_cloudinary",
        lambda **_kwargs: url_cloudinary,
    )
    categoria = Categoria(nombre="Bikinis", slug="bikinis", activo=True)
    db.add(categoria)
    db.commit()
    db.refresh(categoria)

    payload = {
        "codigo": "WEB-BIK-001",
        "nombre": "Bikini creado en la web",
        "descripcion": "Producto de prueba",
        "categoria_id": categoria.id,
        "subcategoria_id": None,
        "marca_id": None,
        "precio_mayorista": 15000,
        "precio_24_productos": 13500,
        "cantidad_unidades_por_bulto": 1,
        "talles": [{"talle": "S", "cantidad": 3}, {"talle": "M", "cantidad": 2}],
        "habilitado": True,
        "visible_tienda": True,
    }
    creado = client.post("/api/admin/productos/", json=payload)
    assert creado.status_code == 201, creado.text
    producto_id = creado.json()["id"]

    producto = db.scalar(select(Producto).where(Producto.id == producto_id))
    assert producto is not None
    assert producto.origen == "web"
    assert sum(item.cantidad for item in producto.stocks_talles) == 5

    png = b"\x89PNG\r\n\x1a\n" + b"contenido-de-prueba"
    imagen = client.post(f"/api/admin/productos/{producto_id}/imagenes", json={
        "nombre": "bikini.png",
        "media_type": "image/png",
        "contenido_base64": base64.b64encode(png).decode(),
        "principal": True,
    })
    assert imagen.status_code == 201, imagen.text
    imagen_id = imagen.json()["id"]
    imagen_guardada = db.get(ImagenProducto, imagen_id)
    assert imagen_guardada.url == url_cloudinary
    assert imagen_guardada.contenido is None

    payload["nombre"] = "Bikini web actualizado"
    payload["talles"] = [{"talle": "S", "cantidad": 4}, {"talle": "M", "cantidad": 2}]
    editado = client.put(f"/api/admin/productos/{producto_id}", json=payload)
    assert editado.status_code == 200, editado.text

    db.expire_all()
    producto = db.get(Producto, producto_id)
    assert producto.nombre == "Bikini web actualizado"
    assert sum(item.cantidad for item in producto.stocks_talles) == 6


def test_admin_crea_producto_sin_sku_y_genera_codigo_interno(client, db):
    response = client.post("/api/admin/productos/", json={
        "codigo": "",
        "nombre": "Producto sin SKU",
        "precio_mayorista": 10000,
        "talles": [{"talle": "Único", "cantidad": 4}],
    })

    assert response.status_code == 201, response.text
    producto = db.get(Producto, response.json()["id"])
    assert producto is not None
    assert producto.dux_codigo == f"WEB-{producto.id}"
    assert producto.codigo_externo is None
