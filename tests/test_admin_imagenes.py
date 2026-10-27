from app.models.migracion_woocommerce import MigracionWooCommerce


def test_diagnostico_de_imagenes_inicia_en_segundo_plano(client, monkeypatch):
    ejecutado = []
    monkeypatch.setattr(
        "app.api.routers.adminImagenesRouter.ejecutar_diagnostico_imagenes_r2_background",
        lambda: ejecutado.append(True),
    )

    response = client.post("/api/admin/imagenes/diagnostico-r2/ejecutar")

    assert response.status_code == 202
    assert response.json()["estado"] == "en_progreso"
    assert ejecutado == [True]


def test_diagnostico_de_imagenes_devuelve_ultimo_informe(client, db):
    db.add(MigracionWooCommerce(
        tipo="diagnostico_imagenes_r2",
        id_externo="catalogo",
        checksum="a" * 64,
        datos={
            "estado": "completado",
            "error": None,
            "resultado": {"solo_lectura": True, "imagenes_total": 3},
        },
    ))
    db.commit()

    response = client.get("/api/admin/imagenes/diagnostico-r2")

    assert response.status_code == 200
    assert response.json()["estado"] == "completado"
    assert response.json()["resultado"]["imagenes_total"] == 3


def test_diagnostico_de_imagenes_requiere_autenticacion(public_client):
    response = public_client.get("/api/admin/imagenes/diagnostico-r2")
    assert response.status_code == 401
