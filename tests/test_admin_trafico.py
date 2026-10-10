def _trafico_prueba(dias: int, fecha=None):
    return {
        "dias": dias,
        "fecha": fecha.isoformat() if fecha else None,
        "resumen": {
            "usuarios": 18,
            "sesiones": 23,
            "vistas_paginas": 65,
            "usuarios_activos_ahora": 2,
        },
        "serie_diaria": [{
            "fecha": "2026-10-10",
            "etiqueta": "10/10",
            "usuarios": 18,
            "sesiones": 23,
            "vistas_paginas": 65,
        }],
        "paginas_populares": [{"ruta": "/", "vistas_paginas": 30, "usuarios": 12}],
        "dispositivos": [{"dispositivo": "mobile", "usuarios": 14}],
        "actualizado_en": "2026-10-10T12:00:00+00:00",
        "fuente": "Google Analytics 4",
    }


def test_admin_total_puede_ver_trafico_sin_exponer_credenciales(client, monkeypatch):
    monkeypatch.setattr(
        "app.api.routers.adminTraficoRouter.obtener_trafico_ga4",
        _trafico_prueba,
    )

    response = client.get("/api/admin/trafico?dias=7")

    assert response.status_code == 200
    assert response.json()["resumen"]["usuarios"] == 18
    assert "credential" not in response.text.lower()


def test_trafico_rechaza_periodos_fuera_de_los_disponibles(client):
    response = client.get("/api/admin/trafico?dias=14")

    assert response.status_code == 422


def test_admin_puede_consultar_un_dia_especifico(client, monkeypatch):
    monkeypatch.setattr(
        "app.api.routers.adminTraficoRouter.obtener_trafico_ga4",
        _trafico_prueba,
    )

    response = client.get("/api/admin/trafico?fecha=2026-10-09")

    assert response.status_code == 200
    assert response.json()["fecha"] == "2026-10-09"


def test_servicio_acepta_fecha_como_texto(monkeypatch):
    from app.services import ga4_analytics_service as service

    monkeypatch.setattr(service, "_sesion_ga4", lambda: object())
    monkeypatch.setattr(service, "_obtener_activos_ahora", lambda _session: 0)
    def reporte_con_dia(*_args, **kwargs):
        if kwargs.get("limit") == 9:
            return {"rows": [{
                "dimensionValues": [{"value": "20261009"}],
                "metricValues": [{"value": "4"}, {"value": "5"}, {"value": "7"}],
            }]}
        return {"rows": []}

    monkeypatch.setattr(service, "_consulta_normal", reporte_con_dia)

    result = service.obtener_trafico_ga4(7, "2026-10-09")

    assert result["fecha"] == "2026-10-09"
    assert result["serie_diaria"][0]["fecha"] == "2026-10-09"


def test_visitante_no_puede_ver_trafico(public_client):
    assert public_client.get("/api/admin/trafico").status_code == 401
