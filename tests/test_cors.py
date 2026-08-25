from fastapi.testclient import TestClient


def test_cors_permite_frontend_local(
    client: TestClient,
):
    response = client.options(
        "/api/productos/",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "GET",
        },
    )

    assert response.status_code == 200
    assert response.headers[
        "access-control-allow-origin"
    ] == "http://localhost:5173"
    assert response.headers[
        "access-control-allow-credentials"
    ] == "true"


def test_cors_no_autoriza_origen_desconocido(
    client: TestClient,
):
    response = client.options(
        "/api/productos/",
        headers={
            "Origin": "https://sitio-desconocido.example",
            "Access-Control-Request-Method": "GET",
        },
    )

    assert response.status_code == 400
    assert (
        "access-control-allow-origin"
        not in response.headers
    )
