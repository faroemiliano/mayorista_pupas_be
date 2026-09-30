import httpx

from app.integrations.dux.client import DuxClient


def test_dux_reintenta_http_429_respetando_espera_minima(monkeypatch):
    respuestas = []
    esperas = []

    def fake_get(url, **_kwargs):
        request = httpx.Request("GET", url)
        respuestas.append(url)
        if len(respuestas) == 1:
            return httpx.Response(
                429,
                request=request,
                headers={"Retry-After": "0"},
                json={"error": "rate limit"},
            )
        return httpx.Response(200, request=request, json={"datos": []})

    monkeypatch.setattr(
        DuxClient,
        "_wait_for_rate_limit",
        classmethod(lambda _cls: None),
    )
    monkeypatch.setattr("app.integrations.dux.client.httpx.get", fake_get)
    monkeypatch.setattr("app.integrations.dux.client.time.sleep", esperas.append)

    resultado = DuxClient().get("v2/items", params={"limit": 1}, reintentos=2)

    assert resultado == {"datos": []}
    assert len(respuestas) == 2
    assert esperas == [5.0]
