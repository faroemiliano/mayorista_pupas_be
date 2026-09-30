from app.models.stock_talle_producto import StockTalleProducto
from app.models.imagen_producto import ImagenProducto
from app.models.producto import Producto
from app.services.dux_sync_service import comparar_stock_dux, sincronizar_catalogo_dux, sincronizar_producto_desde_dux
import httpx


def _producto_dux(stocks: list[dict]) -> dict:
    return {
        "cod_item": "DUX-TALLES-1",
        "item": "Remera de prueba",
        "habilitado": True,
        "precios": [],
        "stock": stocks,
        "codigos_barra": [],
    }


def _stock(talle: str | None, cantidad: int, deposito_id: int) -> dict:
    return {
        "id": deposito_id,
        "nombre": f"Depósito {deposito_id}",
        "stock_real": cantidad,
        "stock_reservado": 0,
        "stock_disponible": cantidad,
        "id_det_item": deposito_id,
        "talle": talle,
    }


def test_dux_no_crea_talles_en_la_tienda(db):
    producto = sincronizar_producto_desde_dux(
        db,
        _producto_dux(
            [
                _stock("Talle 1", 3, 1),
                _stock("1", 2, 2),
                _stock("2", 4, 3),
            ]
        ),
    )

    assert list(producto.stocks_talles) == []


def test_dux_preserva_talles_web_aunque_informe_talles(db):
    producto = sincronizar_producto_desde_dux(
        db,
        _producto_dux([_stock(None, 9, 1)]),
    )
    producto.stocks_talles.extend([
        StockTalleProducto(talle="1", cantidad=3, origen="wordpress"),
        StockTalleProducto(talle="2", cantidad=6, origen="manual"),
    ])
    db.flush()

    stock_1 = _stock("1", 3, 2169)
    stock_1["id_det_item"] = 101
    stock_2 = _stock("2", 4, 2169)
    stock_2["id_det_item"] = 102
    sincronizar_producto_desde_dux(db, _producto_dux([stock_1, stock_2]))

    assert [(fila.talle, fila.cantidad, fila.origen) for fila in producto.stocks_talles] == [
        ("1", 3, "wordpress"),
        ("2", 6, "manual"),
    ]


def test_preserva_talles_manuales_si_dux_no_informa_talles_validos(db):
    producto = sincronizar_producto_desde_dux(
        db,
        _producto_dux([_stock(None, 9, 1)]),
    )
    producto.stocks_talles.extend(
        [
            StockTalleProducto(talle=1, cantidad=3, origen="manual"),
            StockTalleProducto(talle=2, cantidad=6, origen="manual"),
        ]
    )
    db.flush()

    sincronizar_producto_desde_dux(
        db,
        _producto_dux([_stock(None, 12, 1)]),
    )

    assert [(fila.talle, fila.cantidad, fila.origen) for fila in producto.stocks_talles] == [
        (1, 3, "manual"),
        (2, 6, "manual"),
    ]


def test_talles_dux_no_reemplazan_distribucion_de_otras_fuentes(db):
    producto = sincronizar_producto_desde_dux(
        db,
        _producto_dux([_stock(None, 9, 1)]),
    )
    producto.stocks_talles.extend([
        StockTalleProducto(talle="S", cantidad=3, origen="wordpress"),
        StockTalleProducto(talle="M", cantidad=6, origen="manual"),
    ])
    db.flush()

    sincronizar_producto_desde_dux(
        db,
        _producto_dux([_stock("Único", 12, 1)]),
    )

    assert [(fila.talle, fila.cantidad, fila.origen) for fila in producto.stocks_talles] == [
        ("S", 3, "wordpress"),
        ("M", 6, "manual"),
    ]


def test_producto_vinculado_preserva_presentacion_wordpress_al_actualizar_desde_dux(db):
    producto = Producto(
        wordpress_id=50, origen="wordpress_dux", dux_codigo="DUX-TALLES-1",
        nombre="Nombre comercial WordPress", slug="nombre-comercial-wordpress",
        descripcion="Descripción WordPress", imagen_url="https://wordpress.test/principal.jpg",
    )
    producto.imagenes.append(ImagenProducto(
        url="https://wordpress.test/principal.jpg", orden=0, principal=True,
    ))
    db.add(producto)
    db.flush()

    datos_dux = _producto_dux([_stock("4", 7, 1)]) | {
        "item": "Nombre interno Dux", "descripcion": "Descripción Dux",
        "imagen_url": "https://dux.test/imagen.jpg",
    }
    sincronizar_producto_desde_dux(db, datos_dux)

    assert producto.nombre == "Nombre comercial WordPress"
    assert producto.descripcion == "Descripción WordPress"
    assert producto.imagen_url == "https://wordpress.test/principal.jpg"
    assert [imagen.url for imagen in producto.imagenes] == ["https://wordpress.test/principal.jpg"]
    assert list(producto.stocks_talles) == []


def test_catalogo_envia_deposito_pero_no_id_empresa_al_listar_items(db, monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "DUX_ID_DEPOSITO", 2169)
    parametros_recibidos = []

    def fake_get(_self, endpoint, params, reintentos=3):
        parametros_recibidos.append(params)
        assert endpoint == "v2/items"
        return {
            "datos": [_producto_dux([_stock(None, 9, 1)])],
            "paginacion": {"total": 1, "offset": 0, "limit": 50, "hay_mas": False},
        }

    monkeypatch.setattr("app.services.dux_sync_service.DuxClient.get", fake_get)

    resultado = sincronizar_catalogo_dux(db)

    assert resultado["procesados"] == 1
    assert parametros_recibidos == [{"limit": 50, "offset": 0, "id_deposito": 2169}]


def test_catalogo_aisla_registro_que_dux_no_puede_formatear(db, monkeypatch):
    def error_formato():
        request = httpx.Request("GET", "https://dux.test/v2/items")
        response = httpx.Response(400, request=request, json={"error": {"mensaje": "Formato desconocido."}})
        return httpx.HTTPStatusError("error", request=request, response=response)

    def fake_get(_self, endpoint, params, reintentos=3):
        if params["limit"] == 50:
            raise error_formato()
        if params["offset"] == 0:
            return {
                "datos": [_producto_dux([_stock(None, 9, 1)])],
                "paginacion": {"total": 2, "offset": 0, "limit": 1, "hay_mas": True},
            }
        raise error_formato()

    monkeypatch.setattr("app.services.dux_sync_service.DuxClient.get", fake_get)
    resultado = sincronizar_catalogo_dux(db)

    assert resultado["procesados"] == 1
    assert resultado["errores"] == 1
    assert resultado["offsets_omitidos"] == [1]
    assert resultado["deshabilitados_ausentes"] == 0


def test_catalogo_deshabilita_producto_wordpress_vinculado_ausente_en_dux(db, monkeypatch):
    ausente = Producto(
        wordpress_id=80,
        origen="wordpress_dux",
        dux_codigo="YA-NO-EXISTE",
        nombre="Producto retirado",
        slug="producto-retirado",
        conciliacion_estado="vinculado",
        habilitado=True,
    )
    db.add(ausente)
    db.commit()

    monkeypatch.setattr(
        "app.services.dux_sync_service.DuxClient.get",
        lambda _self, _endpoint, params, reintentos=3: {
            "datos": [_producto_dux([_stock(None, 9, 1)])],
            "paginacion": {"total": 1, "offset": 0, "limit": 50, "hay_mas": False},
        },
    )

    resultado = sincronizar_catalogo_dux(db)
    db.refresh(ausente)

    assert resultado["deshabilitados_ausentes"] == 1
    assert ausente.habilitado is False


def test_auditoria_distingue_snapshot_desactualizado_y_producto_web_sin_vinculo(db, monkeypatch):
    from app.core.config import settings
    from app.models.stock_producto import StockProducto

    producto_dux = Producto(
        origen="dux",
        dux_codigo="DUX-AUDITADO",
        nombre="Producto Dux",
        slug="producto-dux-auditado",
        visible_tienda=False,
    )
    producto_dux.stocks.append(StockProducto(
        dux_id_deposito=2169,
        nombre_deposito="Depósito web",
        stock_real=5,
        stock_reservado=0,
        stock_disponible=5,
    ))
    producto_wordpress = Producto(
        wordpress_id=90,
        origen="wordpress",
        dux_codigo="WP-90",
        nombre="Producto sin relacionar",
        slug="producto-sin-relacionar",
        habilitado=True,
        visible_tienda=True,
    )
    producto_wordpress.stocks.append(StockProducto(
        dux_id_deposito=-1,
        nombre_deposito="WordPress temporal",
        stock_real=8,
        stock_reservado=0,
        stock_disponible=8,
    ))
    db.add_all([producto_dux, producto_wordpress])
    db.commit()
    monkeypatch.setattr(settings, "DUX_ID_DEPOSITO", 2169)
    monkeypatch.setattr(
        "app.services.dux_sync_service.DuxClient.get",
        lambda _self, _endpoint, params, reintentos=3: {
            "datos": [{
                "cod_item": "DUX-AUDITADO",
                "item": "Producto Dux",
                "stock": [{"id": 2169, "stock_disponible": 7}],
            }],
            "paginacion": {"total": 1, "offset": 0, "limit": 50, "hay_mas": False},
        },
    )

    resultado = comparar_stock_dux(db)

    assert resultado["total_diferencias_snapshot"] == 1
    assert resultado["diferencias_snapshot"][0]["stock_dux"] == 7.0
    assert resultado["diferencias_snapshot"][0]["stock_snapshot_local"] == 5.0
    assert resultado["productos_web_sin_vinculo"]["total"] == 1
    assert resultado["listo_para_activar"] is False


def test_panel_bloquea_sincronizacion_dux_en_modo_wordpress(client, monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "DUX_SINCRONIZACION_HABILITADA", False)
    configuracion = client.get("/api/admin/configuracion/dux")
    assert configuracion.status_code == 200
    assert configuracion.json()["modo"] == "wordpress"
    assert configuracion.json()["sincronizacion_habilitada"] is False
    assert client.post("/api/admin/productos/sincronizar").status_code == 409
    assert client.post("/api/admin/clientes-dux/sincronizar").status_code == 409
