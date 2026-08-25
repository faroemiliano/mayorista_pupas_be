from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.categoria import Categoria
from app.models.marca import Marca
from app.models.precio_producto import PrecioProducto
from app.models.producto import Producto
from app.models.stock_producto import StockProducto
from app.models.subcategoria import Subcategoria


def crear_catalogo(db: Session) -> dict[str, int]:
    categoria = Categoria(
        dux_id=10,
        nombre="Bebés",
        slug="bebes",
        activo=True,
    )
    categoria_inactiva = Categoria(
        dux_id=20,
        nombre="Inactiva",
        slug="inactiva",
        activo=False,
    )

    abrigos = Subcategoria(
        dux_id=11,
        nombre="Abrigos",
        slug="bebes-abrigos",
        activo=True,
    )
    zapatitos = Subcategoria(
        dux_id=12,
        nombre="Zapatitos",
        slug="bebes-zapatitos",
        activo=True,
    )
    subcategoria_inactiva = Subcategoria(
        dux_id=13,
        nombre="Oculta",
        slug="bebes-oculta",
        activo=False,
    )

    categoria.subcategorias.extend([
        zapatitos,
        abrigos,
        subcategoria_inactiva,
    ])

    marca = Marca(
        dux_id=30,
        nombre="Acme",
        slug="acme",
        activo=True,
    )
    marca_inactiva = Marca(
        dux_id=31,
        nombre="Oculta",
        slug="marca-oculta",
        activo=False,
    )

    producto = Producto(
        dux_codigo="P-001",
        nombre="Campera bebé",
        slug="campera-bebe-p-001",
        habilitado=True,
        categoria=categoria,
        subcategoria=abrigos,
        marca=marca,
    )
    producto.stocks.append(
        StockProducto(
            dux_id_deposito=1,
            nombre_deposito="Central",
            stock_real=5,
            stock_reservado=1,
            stock_disponible=4,
        )
    )
    producto.precios.extend([
        PrecioProducto(
            dux_id_lista=4710,
            nombre_lista="MAYORISTA",
            precio=12000,
        ),
        PrecioProducto(
            dux_id_lista=43406,
            nombre_lista="24 PRODUCTOS",
            precio=10500,
        ),
        PrecioProducto(
            dux_id_lista=22702,
            nombre_lista="MINORISTA",
            precio=15000,
        ),
    ])

    producto_inactivo = Producto(
        dux_codigo="P-002",
        nombre="Producto oculto",
        slug="producto-oculto-p-002",
        habilitado=False,
        categoria=categoria,
        subcategoria=zapatitos,
        marca=marca,
    )

    db.add_all([
        categoria,
        categoria_inactiva,
        marca,
        marca_inactiva,
        producto,
        producto_inactivo,
    ])
    db.commit()

    return {
        "categoria_id": categoria.id,
        "subcategoria_id": abrigos.id,
        "marca_id": marca.id,
        "producto_id": producto.id,
    }


def test_listar_categorias_activas_con_subcategorias(
    client: TestClient,
    db: Session,
):
    crear_catalogo(db)

    response = client.get(
        "/api/categorias/"
    )

    assert response.status_code == 200

    categorias = response.json()

    assert len(categorias) == 1
    assert categorias[0]["nombre"] == "Bebés"
    assert [
        item["nombre"]
        for item in categorias[0]["subcategorias"]
    ] == ["Abrigos", "Zapatitos"]


def test_listar_subcategorias_filtradas_por_categoria(
    client: TestClient,
    db: Session,
):
    ids = crear_catalogo(db)

    response = client.get(
        "/api/subcategorias/",
        params={
            "categoria_id": ids["categoria_id"],
        },
    )

    assert response.status_code == 200

    subcategorias = response.json()

    assert [
        item["nombre"]
        for item in subcategorias
    ] == ["Abrigos", "Zapatitos"]
    assert all(
        item["categoria"]["id"]
        == ids["categoria_id"]
        for item in subcategorias
    )


def test_listar_marcas_activas(
    client: TestClient,
    db: Session,
):
    crear_catalogo(db)

    response = client.get(
        "/api/marcas/"
    )

    assert response.status_code == 200
    assert [
        item["nombre"]
        for item in response.json()
    ] == ["Acme"]


def test_filtrar_productos_del_catalogo(
    client: TestClient,
    db: Session,
):
    ids = crear_catalogo(db)

    response = client.get(
        "/api/productos/",
        params={
            "categoria_id": ids["categoria_id"],
            "subcategoria_id": ids["subcategoria_id"],
            "marca_id": ids["marca_id"],
            "con_stock": True,
        },
    )

    assert response.status_code == 200

    resultado = response.json()

    assert resultado["total"] == 1
    assert resultado["items"][0]["dux_codigo"] == "P-001"
    assert resultado["items"][0]["precio_mayorista"] == "12000.00"
    assert resultado["items"][0]["precio_24_productos"] == "10500.00"
    assert "precios" not in resultado["items"][0]
    assert "costo" not in resultado["items"][0]


def test_obtener_recursos_por_slug_y_responder_404(
    client: TestClient,
    db: Session,
):
    crear_catalogo(db)

    assert client.get(
        "/api/categorias/slug/bebes"
    ).status_code == 200
    assert client.get(
        "/api/subcategorias/slug/bebes-abrigos"
    ).status_code == 200
    assert client.get(
        "/api/marcas/slug/acme"
    ).status_code == 200
    assert client.get(
        "/api/productos/slug/campera-bebe-p-001"
    ).status_code == 200
    assert client.get(
        "/api/productos/999999"
    ).status_code == 404


def test_incluir_entidades_inactivas_bajo_demanda(
    client: TestClient,
    db: Session,
):
    crear_catalogo(db)

    categorias = client.get(
        "/api/categorias/",
        params={"solo_activas": False},
    ).json()
    marcas = client.get(
        "/api/marcas/",
        params={"solo_activas": False},
    ).json()

    assert len(categorias) == 2
    assert len(marcas) == 2


def test_precio_24_invalido_conserva_precio_mayorista(
    client: TestClient,
    db: Session,
):
    ids = crear_catalogo(db)

    precio_24 = db.scalar(
        select(PrecioProducto).where(
            PrecioProducto.producto_id
            == ids["producto_id"],
            PrecioProducto.dux_id_lista
            == 43406,
        )
    )
    precio_24.precio = 0
    db.commit()

    producto = client.get(
        f"/api/productos/{ids['producto_id']}"
    ).json()

    assert producto["precio_mayorista"] == "12000.00"
    assert producto["precio_24_productos"] == "12000.00"
