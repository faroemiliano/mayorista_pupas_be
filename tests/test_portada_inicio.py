import base64

from fastapi.testclient import TestClient

from app.core.security import get_usuario_opcional
from app.main import app
from app.models.portada_inicio import PortadaInicio
from app.models.imagen_producto import ImagenProducto
from app.models.categoria import Categoria
from app.models.producto import Producto
from app.models.usuario import Usuario


def test_admin_tecnico_actualiza_una_portada_en_r2(client: TestClient, db, monkeypatch):
    monkeypatch.setattr(
        "app.api.routers.portadaInicioRouter.subir_imagen_portada_a_r2",
        lambda **_: "https://imagenes.pupasmayorista.com.ar/pupas/sitio/portada/bikinis/nueva.webp",
    )
    contenido = base64.b64encode(b"RIFF\x00\x00\x00\x00WEBPcontenido").decode()

    response = client.put(
        "/api/admin/portada/bikinis",
        json={
            "nombre": "portada.webp",
            "media_type": "image/webp",
            "contenido_base64": contenido,
        },
    )

    assert response.status_code == 200
    assert response.json() == {
        "slide_id": "bikinis",
        "imagen_url": "https://imagenes.pupasmayorista.com.ar/pupas/sitio/portada/bikinis/nueva.webp",
    }
    assert db.query(PortadaInicio).filter_by(slide_id="bikinis").one().media_type == "image/webp"

    publica = client.get("/api/portada")
    assert publica.status_code == 200
    assert publica.json()["imagenes"]["bikinis"].endswith("/nueva.webp")


def test_portada_rechaza_un_slide_inexistente(client: TestClient):
    response = client.put(
        "/api/admin/portada/otro",
        json={
            "nombre": "portada.webp",
            "media_type": "image/webp",
            "contenido_base64": base64.b64encode(b"RIFF\x00\x00\x00\x00WEBPcontenido").decode(),
        },
    )

    assert response.status_code == 404


def test_admin_puede_guardar_una_foto_manual_de_coleccion(client: TestClient, monkeypatch):
    monkeypatch.setattr(
        "app.api.routers.portadaInicioRouter.subir_imagen_portada_a_r2",
        lambda **_: "https://imagenes.pupasmayorista.com.ar/pupas/sitio/portada/coleccion-bikinis-1/nueva.webp",
    )

    response = client.put(
        "/api/admin/portada/coleccion-bikinis-1",
        json={
            "nombre": "bikini-elegida.webp",
            "media_type": "image/webp",
            "contenido_base64": base64.b64encode(b"RIFF\x00\x00\x00\x00WEBPcontenido").decode(),
        },
    )

    assert response.status_code == 200
    assert response.json()["slide_id"] == "coleccion-bikinis-1"


def test_admin_puede_reutilizar_una_imagen_r2_del_catalogo(client: TestClient, db, monkeypatch):
    monkeypatch.setattr(
        "app.api.routers.portadaInicioRouter.settings.R2_PUBLIC_BASE_URL",
        "https://imagenes.pupasmayorista.com.ar",
    )
    categoria = Categoria(nombre="Bikinis selector", slug="bikinis-selector")
    producto = Producto(
        dux_codigo="WEB-PORTADA-1",
        nombre="Bikini para portada",
        slug="bikini-para-portada",
        origen="web",
        categoria=categoria,
    )
    producto.imagenes.append(
        ImagenProducto(
            url="https://imagenes.pupasmayorista.com.ar/pupas/catalogo/productos/1/imagenes/1.webp",
            media_type="image/webp",
            orden=0,
            principal=True,
        )
    )
    db.add(producto)
    db.commit()

    response = client.put(
        "/api/admin/portada/coleccion-bikinis-1/imagen-producto",
        json={"imagen_id": producto.imagenes[0].id},
    )

    assert response.status_code == 200
    assert response.json()["imagen_url"] == producto.imagenes[0].url

    selector = client.get(f"/api/admin/portada/imagenes-producto?categoria_id={categoria.id}")
    assert selector.status_code == 200
    assert selector.json()["total"] == 1
    assert selector.json()["items"][0]["id"] == producto.imagenes[0].id


def test_admin_prepara_y_confirma_la_carga_directa_de_un_video(client: TestClient, monkeypatch):
    monkeypatch.setattr(
        "app.api.routers.portadaInicioRouter.crear_carga_directa_video_portada",
        lambda **_: {
            "clave": "pupas/sitio/videos/video-bikinis/archivo.mp4",
            "upload_url": "https://r2.example/upload",
            "video_url": "https://imagenes.pupasmayorista.com.ar/pupas/sitio/videos/video-bikinis/archivo.mp4",
        },
    )
    preparacion = client.post(
        "/api/admin/portada/video-bikinis/video/carga",
        json={"nombre": "campania.mp4", "media_type": "video/mp4", "tamano": 1024},
    )
    assert preparacion.status_code == 200

    monkeypatch.setattr(
        "app.api.routers.portadaInicioRouter.confirmar_video_portada_en_r2",
        lambda **_: "https://imagenes.pupasmayorista.com.ar/pupas/sitio/videos/video-bikinis/archivo.mp4",
    )
    confirmacion = client.put(
        "/api/admin/portada/video-bikinis/video/confirmar",
        json={"clave": preparacion.json()["clave"]},
    )
    assert confirmacion.status_code == 200
    assert confirmacion.json()["slide_id"] == "video-bikinis"


def test_operador_no_puede_cambiar_fotos_de_portada(client: TestClient):
    app.dependency_overrides[get_usuario_opcional] = lambda: Usuario(
        id=2,
        email="operador@test.local",
        nombre="Operador",
        rol="admin_operativo",
        activo=True,
    )

    response = client.put(
        "/api/admin/portada/bikinis",
        json={
            "nombre": "portada.webp",
            "media_type": "image/webp",
            "contenido_base64": base64.b64encode(b"RIFF\x00\x00\x00\x00WEBPcontenido").decode(),
        },
    )

    assert response.status_code == 403
