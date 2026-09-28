from app.models.stock_talle_producto import StockTalleProducto
from app.models.imagen_producto import ImagenProducto
from app.models.producto import Producto
from app.services.dux_sync_service import sincronizar_catalogo_dux, sincronizar_producto_desde_dux
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


def test_importa_y_suma_stock_por_talle_desde_dux(db):
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

    stock = {fila.talle: fila for fila in producto.stocks_talles}

    assert {talle: item.cantidad for talle, item in stock.items()} == {"1": 5, "2": 4}
    assert all(fila.origen == "dux" for fila in stock.values())


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
        _producto_dux([_stock("Único", 12, 1)]),
    )

    assert [(fila.talle, fila.cantidad, fila.origen) for fila in producto.stocks_talles] == [
        (1, 3, "manual"),
        (2, 6, "manual"),
        ("Único", 12, "dux"),
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
    assert {stock.talle: stock.cantidad for stock in producto.stocks_talles} == {"4": 7}


def test_catalogo_no_envia_id_empresa_al_listar_items(db, monkeypatch):
    parametros_recibidos = []

    def fake_get(_self, endpoint, params, reintentos=3):
        parametros_recibidos.append(params)
        assert endpoint == "v2/items"
        return {
            "datos": [_producto_dux([_stock(None, 9, 1)])],
            "paginacion": {"total": 1, "offset": 0, "limit": 20, "hay_mas": False},
        }

    monkeypatch.setattr("app.services.dux_sync_service.DuxClient.get", fake_get)

    resultado = sincronizar_catalogo_dux(db)

    assert resultado["procesados"] == 1
    assert parametros_recibidos == [{"limit": 20, "offset": 0}]


def test_catalogo_aisla_registro_que_dux_no_puede_formatear(db, monkeypatch):
    def error_formato():
        request = httpx.Request("GET", "https://dux.test/v2/items")
        response = httpx.Response(400, request=request, json={"error": {"mensaje": "Formato desconocido."}})
        return httpx.HTTPStatusError("error", request=request, response=response)

    def fake_get(_self, endpoint, params, reintentos=3):
        if params["limit"] == 20:
            raise error_formato()
        if params["offset"] == 0:
            return {
                "datos": [_producto_dux([_stock(None, 9, 1)])],
                "paginacion": {"total": 2, "offset": 0, "limit": 1, "hay_mas": True},
            }
        raise error_formato()

    monkeypatch.setattr("app.services.dux_sync_service.DuxClient.get", fake_get)
    monkeypatch.setattr("app.services.dux_sync_service.time.sleep", lambda _seconds: None)

    resultado = sincronizar_catalogo_dux(db)

    assert resultado["procesados"] == 1
    assert resultado["errores"] == 1
    assert resultado["offsets_omitidos"] == [1]
    assert resultado["deshabilitados_ausentes"] == 0


def test_panel_bloquea_sincronizacion_dux_en_modo_wordpress(client, monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "DUX_SINCRONIZACION_HABILITADA", False)
    configuracion = client.get("/api/admin/configuracion/dux")
    assert configuracion.status_code == 200
    assert configuracion.json()["modo"] == "wordpress"
    assert configuracion.json()["sincronizacion_habilitada"] is False
    assert client.post("/api/admin/productos/sincronizar").status_code == 409
    assert client.post("/api/admin/clientes-dux/sincronizar").status_code == 409
