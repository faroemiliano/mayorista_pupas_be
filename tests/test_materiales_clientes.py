import base64

from app.models.notificacion import Notificacion
from app.models.usuario import Usuario
from sqlalchemy import select


PNG_MINIMO = b"\x89PNG\r\n\x1a\ncontenido-de-prueba"


def test_admin_publica_y_elimina_material_para_clientes(client, db):
    cliente = Usuario(
        email="material@test.local",
        nombre="Cliente Material",
        rol="cliente",
        estado_registro="aprobado",
    )
    db.add(cliente)
    db.commit()

    response = client.post("/api/admin/materiales-clientes/", json={
        "titulo": "Foto campaña",
        "descripcion": "Lista para redes",
        "nombre_archivo": "campana.png",
        "contenido_base64": base64.b64encode(PNG_MINIMO).decode(),
    })
    assert response.status_code == 201, response.text
    material_id = response.json()["id"]

    listado = client.get("/api/materiales-clientes/")
    assert listado.status_code == 200
    assert listado.json()[0]["titulo"] == "Foto campaña"

    archivo = client.get(f"/api/materiales-clientes/{material_id}/archivo")
    assert archivo.status_code == 200
    assert archivo.content == PNG_MINIMO
    assert archivo.headers["content-type"] == "image/png"

    notificacion = db.scalar(select(Notificacion).where(Notificacion.usuario_id == cliente.id))
    assert notificacion is not None
    assert notificacion.tipo == "material_nuevo"

    eliminado = client.delete(f"/api/admin/materiales-clientes/{material_id}")
    assert eliminado.status_code == 204
    assert client.get("/api/materiales-clientes/").json() == []


def test_visitante_no_puede_acceder_al_material(public_client):
    assert public_client.get("/api/materiales-clientes/").status_code == 401


def test_admin_publica_varias_imagenes_con_una_sola_notificacion(client, db):
    cliente = Usuario(
        email="lote@test.local", nombre="Cliente Lote", rol="cliente", estado_registro="aprobado"
    )
    db.add(cliente)
    db.commit()
    contenido = base64.b64encode(PNG_MINIMO).decode()

    response = client.post("/api/admin/materiales-clientes/lote", json={
        "titulo": "Campaña completa",
        "descripcion": "Fotos para publicar",
        "archivos": [
            {"nombre_archivo": "foto-1.png", "contenido_base64": contenido},
            {"nombre_archivo": "foto-2.png", "contenido_base64": contenido},
        ],
    })

    assert response.status_code == 201, response.text
    assert len(response.json()) == 2
    notificaciones = db.scalars(select(Notificacion).where(Notificacion.usuario_id == cliente.id)).all()
    assert len(notificaciones) == 1
    assert "2 nuevas imágenes" in notificaciones[0].mensaje
