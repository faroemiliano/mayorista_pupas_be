def test_auditoria_stock_se_ejecuta_en_background_y_evita_duplicados(client, monkeypatch):
    monkeypatch.setattr(
        "app.api.routers.adminConfiguracionRouter.ejecutar_auditoria_stock_dux_background",
        lambda _ejecucion_id: None,
    )

    inicio = client.post("/api/admin/configuracion/dux/comparar-stock")
    repetida = client.post("/api/admin/configuracion/dux/comparar-stock")
    estado = client.get("/api/admin/configuracion/dux/auditoria-stock")

    assert inicio.status_code == 202
    assert inicio.json()["estado"] == "en_progreso"
    assert repetida.status_code == 409
    assert estado.status_code == 200
    assert estado.json()["estado"] == "en_progreso"


def test_modo_dux_depende_de_la_fuente_de_stock(client, monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "DUX_ESCRITURA_HABILITADA", False)
    monkeypatch.setattr(settings, "DUX_SINCRONIZACION_HABILITADA", True)

    respuesta = client.get("/api/admin/configuracion/dux")

    assert respuesta.status_code == 200
    assert respuesta.json() == {
        "escritura_habilitada": False,
        "sincronizacion_habilitada": True,
        "modo": "produccion",
    }
