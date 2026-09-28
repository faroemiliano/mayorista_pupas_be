from app.models.migracion_woocommerce import MigracionWooCommerce
from app.models.producto import Producto


def test_admin_puede_ver_resumen_de_staging(client, db):
    db.add_all([
        MigracionWooCommerce(tipo="producto", id_externo="10", checksum="a" * 64, datos={
            "id": 10, "name": "Pijama prueba", "status": "publish", "type": "variable",
            "images": [{"src": "https://example.com/pijama.jpg"}],
            "_variaciones_completas": [
                {"price": "100", "stock_quantity": 2, "attributes": [{"name": "Talle", "option": "1"}]},
                {"price": "100", "stock_quantity": 3, "attributes": [{"name": "Talle", "option": "2"}]},
            ],
        }),
        MigracionWooCommerce(tipo="cliente", id_externo="20", checksum="b" * 64, datos={
            "id": 20, "email": "cliente@example.com", "first_name": "Ana", "last_name": "Pérez",
            "billing": {"phone": "112233", "city": "Rosario", "state": "S", "address_1": "Calle 1"},
        }),
        MigracionWooCommerce(tipo="pedido", id_externo="30", checksum="c" * 64, datos={
            "id": 30, "number": "15909", "status": "completed", "customer_id": 20,
            "total": "200", "currency": "ARS", "line_items": [{"quantity": 2}],
        }),
    ])
    db.commit()

    response = client.get("/api/admin/migracion-wordpress/resumen")

    assert response.status_code == 200
    data = response.json()
    assert data["solo_lectura"] is True
    assert data["totales"] == {"productos": 1, "clientes": 1, "pedidos": 1}
    assert data["productos"][0]["stock_total"] == 5
    assert data["productos"][0]["talles"] == ["1", "2"]
    assert data["clientes"][0]["email"] == "cliente@example.com"
    assert data["pedidos"][0]["cantidad_unidades"] == 2


def test_resumen_de_staging_requiere_admin(public_client):
    response = public_client.get("/api/admin/migracion-wordpress/resumen")
    assert response.status_code == 401


def test_admin_revisa_y_vincula_candidato_dudoso(client, db):
    db.add_all([
        Producto(wordpress_id=10, origen="wordpress", dux_codigo="WP-10", nombre="Pijama Luna", slug="pijama-luna"),
        MigracionWooCommerce(
            tipo="conciliacion", id_externo="productos-wordpress-dux", checksum="d" * 64,
            datos={
                "totales": {"wordpress": 1, "dux": 1, "coincidencias": 0, "dudosos": 1, "solo_wordpress": 0, "solo_dux": 0},
                "coincidencias": [], "solo_wordpress": [], "solo_dux": [],
                "dudosos": [{"wordpress_id": "10", "wordpress_nombre": "Pijama Luna", "dux_codigo_sugerido": "A1", "dux_nombre_sugerido": "Pijama Lunna", "similitud": .95}],
            },
        ),
    ])
    db.commit()

    pendientes = client.get("/api/admin/migracion-wordpress/conciliacion-productos/dudosos")
    assert pendientes.status_code == 200
    assert pendientes.json()["total"] == 1

    vinculacion = client.post("/api/admin/migracion-wordpress/conciliacion-productos/vincular", json={"wordpress_id": 10, "dux_codigo": "A1"})
    assert vinculacion.status_code == 200, vinculacion.text
    assert vinculacion.json()["estado"] == "vinculado"
    assert client.get("/api/admin/migracion-wordpress/conciliacion-productos/dudosos").json()["total"] == 0


def test_admin_inicia_importacion_protegida_en_segundo_plano(client, monkeypatch):
    ejecutado = []
    monkeypatch.setattr(
        "app.api.routers.adminMigracionWordpressRouter.ejecutar_migracion_wordpress_background",
        lambda: ejecutado.append(True),
    )

    response = client.post("/api/admin/migracion-wordpress/ejecutar", json={"confirmar": True})
    assert response.status_code == 202, response.text
    assert response.json()["estado"] == "en_progreso"
    assert ejecutado == [True]
    estado = client.get("/api/admin/migracion-wordpress/ejecucion")
    assert estado.status_code == 200
    assert estado.json()["etapa"] == "preparando"
