from sqlalchemy.orm import Session

from app.models.migracion_woocommerce import MigracionWooCommerce
from app.models.producto import Producto
from app.services import conciliacion_productos_background_service as conciliacion_background
from app.core.config import settings


def _habilitar_acciones_migracion(monkeypatch):
    monkeypatch.setattr(settings, "MIGRACION_WORDPRESS_ACCIONES_HABILITADAS", True)


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
    assert "productos" not in data
    assert "clientes" not in data
    assert data["pedidos"][0]["cantidad_unidades"] == 2


def test_resumen_de_staging_requiere_admin(public_client):
    response = public_client.get("/api/admin/migracion-wordpress/resumen")
    assert response.status_code == 401


def test_acciones_de_migracion_quedan_bloqueadas_por_defecto(client):
    response = client.post(
        "/api/admin/migracion-wordpress/ejecutar",
        json={"confirmar": True},
    )
    assert response.status_code == 403
    assert "bloqueadas" in response.json()["detail"]


def test_admin_revisa_y_vincula_candidato_dudoso(client, db, monkeypatch):
    _habilitar_acciones_migracion(monkeypatch)
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
    _habilitar_acciones_migracion(monkeypatch)
    ejecutado = []
    monkeypatch.setattr(
        "app.api.routers.adminMigracionWordpressRouter.ejecutar_migracion_wordpress_background",
        lambda actualizar_todo=False: ejecutado.append(actualizar_todo),
    )

    response = client.post("/api/admin/migracion-wordpress/ejecutar", json={"confirmar": True, "actualizar_todo": True})
    assert response.status_code == 202, response.text
    assert response.json()["estado"] == "en_progreso"
    assert ejecutado == [True]
    estado = client.get("/api/admin/migracion-wordpress/ejecucion")
    assert estado.status_code == 200
    assert estado.json()["etapa"] == "preparando"


def test_admin_inicia_conciliacion_en_segundo_plano_y_evitar_duplicados(
    client, db, monkeypatch,
):
    _habilitar_acciones_migracion(monkeypatch)
    db.add(MigracionWooCommerce(
        tipo="producto",
        id_externo="10",
        checksum="a" * 64,
        datos={"id": 10, "name": "Pijama Luna"},
    ))
    db.commit()
    ejecuciones = []
    monkeypatch.setattr(
        "app.api.routers.adminMigracionWordpressRouter."
        "ejecutar_generacion_conciliacion_background",
        lambda ejecucion_id: ejecuciones.append(ejecucion_id),
    )

    response = client.post(
        "/api/admin/migracion-wordpress/conciliacion-productos/generar"
    )

    assert response.status_code == 202, response.text
    data = response.json()
    assert data["estado"] == "en_progreso"
    assert data["accion"] == "generar"
    assert data["etapa"] == "preparando"
    assert ejecuciones == [data["ejecucion_id"]]

    estado = client.get(
        "/api/admin/migracion-wordpress/conciliacion-productos/ejecucion"
    )
    assert estado.status_code == 200
    assert estado.json()["ejecucion_id"] == data["ejecucion_id"]

    duplicada = client.post(
        "/api/admin/migracion-wordpress/conciliacion-productos/generar"
    )
    assert duplicada.status_code == 409
    assert "ya está en progreso" in duplicada.json()["detail"]


def test_generacion_background_actualiza_progreso_y_finaliza(db, monkeypatch):
    db.add(MigracionWooCommerce(
        tipo="producto",
        id_externo="10",
        checksum="a" * 64,
        datos={"id": 10, "name": "Pijama Luna"},
    ))
    db.commit()
    monkeypatch.setattr(
        conciliacion_background,
        "SessionLocal",
        lambda: Session(db.get_bind()),
    )

    def generar_falso(_db, progreso):
        progreso(4, 7)
        return {"totales": {"wordpress": 1, "dux": 7, "coincidencias": 1}}

    monkeypatch.setattr(
        conciliacion_background,
        "generar_conciliacion",
        generar_falso,
    )
    preparado = conciliacion_background.preparar_generacion_conciliacion(db)

    conciliacion_background.ejecutar_generacion_conciliacion_background(
        preparado["ejecucion_id"]
    )

    db.expire_all()
    estado = conciliacion_background.obtener_estado_conciliacion(db)
    assert estado["estado"] == "completada"
    assert estado["etapa"] == "finalizada"
    assert estado["progreso"] is None
    assert estado["resultado"]["totales"] == {
        "wordpress": 1,
        "dux": 7,
        "coincidencias": 1,
    }


def test_admin_aplica_coincidencias_seguras_solo_con_confirmacion(client, db, monkeypatch):
    _habilitar_acciones_migracion(monkeypatch)
    producto = Producto(
        wordpress_id=10,
        origen="wordpress",
        dux_codigo="WP-10",
        nombre="Pijama Luna",
        slug="pijama-luna",
    )
    db.add_all([
        producto,
        MigracionWooCommerce(
            tipo="conciliacion",
            id_externo="productos-wordpress-dux",
            checksum="c" * 64,
            datos={
                "totales": {
                    "wordpress": 1,
                    "dux": 1,
                    "coincidencias": 1,
                    "dudosos": 0,
                    "solo_wordpress": 0,
                    "solo_dux": 0,
                },
                "coincidencias": [{
                    "wordpress_id": "10",
                    "wordpress_nombre": "Pijama Luna",
                    "dux_codigo": "A1",
                    "dux_nombre": "Pijama Luna",
                    "criterio": "codigo",
                }],
                "dudosos": [],
                "solo_wordpress": [],
                "solo_dux": [],
            },
        ),
    ])
    db.commit()

    sin_confirmar = client.post(
        "/api/admin/migracion-wordpress/conciliacion-productos/aplicar-seguras",
        json={"confirmar": False},
    )
    assert sin_confirmar.status_code == 422
    db.refresh(producto)
    assert producto.dux_codigo == "WP-10"

    aplicada = client.post(
        "/api/admin/migracion-wordpress/conciliacion-productos/aplicar-seguras",
        json={"confirmar": True},
    )
    assert aplicada.status_code == 200, aplicada.text
    assert aplicada.json()["vinculados"] == 1
    db.refresh(producto)
    assert producto.dux_codigo == "A1"
    assert producto.conciliacion_estado == "vinculado"

    estado = client.get(
        "/api/admin/migracion-wordpress/conciliacion-productos/ejecucion"
    ).json()
    assert estado["estado"] == "completada"
    assert estado["accion"] == "aplicar"
    assert estado["resultado"]["aplicacion"]["vinculados"] == 1


def test_admin_lista_solo_wordpress_y_solo_dux_con_busqueda_y_paginacion(
    client, db,
):
    db.add_all([
        Producto(
            wordpress_id=2,
            origen="wordpress_dux",
            dux_codigo="B2",
            nombre="Producto ya vinculado",
            slug="producto-ya-vinculado",
            conciliacion_estado="vinculado",
        ),
        MigracionWooCommerce(
            tipo="conciliacion",
            id_externo="productos-wordpress-dux",
            checksum="e" * 64,
            datos={
                "totales": {
                    "wordpress": 3,
                    "dux": 3,
                    "coincidencias": 0,
                    "dudosos": 0,
                    "solo_wordpress": 3,
                    "solo_dux": 3,
                },
                "coincidencias": [],
                "dudosos": [],
                "solo_wordpress": [
                    {"wordpress_id": "1", "wordpress_nombre": "Alfa"},
                    {"wordpress_id": "2", "wordpress_nombre": "Vinculado"},
                    {"wordpress_id": "3", "wordpress_nombre": "Gamma"},
                ],
                "solo_dux": [
                    {"dux_codigo": "A1", "dux_nombre": "Dux Alfa"},
                    {"dux_codigo": "B2", "dux_nombre": "Vinculado"},
                    {"dux_codigo": "C3", "dux_nombre": "Dux Gamma"},
                ],
            },
        ),
    ])
    db.commit()

    wordpress = client.get(
        "/api/admin/migracion-wordpress/conciliacion-productos/solo-wordpress",
        params={"page": 2, "limit": 1},
    )
    assert wordpress.status_code == 200
    assert wordpress.json()["total"] == 2
    assert wordpress.json()["total_paginas"] == 2
    assert wordpress.json()["items"] == [
        {"wordpress_id": "3", "wordpress_nombre": "Gamma"}
    ]

    solo_dux = client.get(
        "/api/admin/migracion-wordpress/conciliacion-productos/solo-dux",
        params={"buscar": "gamma"},
    )
    assert solo_dux.status_code == 200
    assert solo_dux.json()["total"] == 1
    assert solo_dux.json()["items"][0]["dux_codigo"] == "C3"
