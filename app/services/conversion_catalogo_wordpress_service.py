from decimal import Decimal, InvalidOperation
from datetime import datetime

from slugify import slugify
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.categoria import Categoria
from app.models.imagen_producto import ImagenProducto
from app.models.migracion_woocommerce import MigracionWooCommerce
from app.models.precio_producto import PrecioProducto
from app.models.producto import Producto
from app.models.stock_producto import StockProducto
from app.models.stock_talle_producto import StockTalleProducto
from app.models.subcategoria import Subcategoria
from app.models.variacion_producto import VariacionProducto


def _decimal(valor) -> Decimal | None:
    try:
        return Decimal(str(valor)) if valor not in (None, "") else None
    except (InvalidOperation, ValueError):
        return None


def _fecha(valor: str | None) -> datetime | None:
    if not valor:
        return None
    try:
        return datetime.fromisoformat(valor.replace("Z", "+00:00"))
    except ValueError:
        return None


def _slug_unico(db: Session, modelo, base: str, id_wordpress: int, actual_id: int | None = None) -> str:
    candidato = slugify(base) or f"wordpress-{id_wordpress}"
    existente = db.scalar(select(modelo.id).where(modelo.slug == candidato))
    if existente is None or existente == actual_id:
        return candidato
    return f"{candidato}-wp-{id_wordpress}"


def _atributos(variacion: dict) -> dict:
    return {
        str(atributo.get("name") or "Atributo"): str(atributo.get("option") or "")
        for atributo in variacion.get("attributes") or []
    }


def _talle(variacion: dict) -> str | None:
    atributos = _atributos(variacion)
    for nombre, valor in atributos.items():
        if any(token in nombre.lower() for token in ("talle", "talla", "size")):
            return valor
    return next(iter(atributos.values()), None)


def convertir_catalogo_wordpress(db: Session, progreso=None) -> dict:
    filas_categorias = db.scalars(select(MigracionWooCommerce).where(MigracionWooCommerce.tipo == "categoria")).all()
    datos_categorias = {int(fila.id_externo): fila.datos for fila in filas_categorias}
    categorias_raiz: dict[int, Categoria] = {}
    subcategorias: dict[int, Subcategoria] = {}

    for wordpress_id, datos in datos_categorias.items():
        if int(datos.get("parent") or 0) != 0:
            continue
        categoria = db.scalar(select(Categoria).where(Categoria.wordpress_id == wordpress_id))
        if categoria is None:
            categoria = db.scalar(select(Categoria).where(Categoria.nombre == datos.get("name")))
        if categoria is None:
            categoria = Categoria(nombre=datos.get("name") or f"Categoría {wordpress_id}", slug="temporal", activo=True)
            db.add(categoria); db.flush()
        categoria.wordpress_id = wordpress_id
        categoria.nombre = datos.get("name") or categoria.nombre
        categoria.slug = _slug_unico(db, Categoria, datos.get("slug") or categoria.nombre, wordpress_id, categoria.id)
        categoria.descripcion = datos.get("description") or None
        categoria.activo = True
        categorias_raiz[wordpress_id] = categoria
    db.flush()

    def raiz_de(wordpress_id: int) -> int:
        actual = wordpress_id
        visitados = set()
        while actual in datos_categorias and actual not in visitados:
            visitados.add(actual)
            padre = int(datos_categorias[actual].get("parent") or 0)
            if padre == 0:
                return actual
            actual = padre
        return wordpress_id

    for wordpress_id, datos in datos_categorias.items():
        if int(datos.get("parent") or 0) == 0:
            continue
        raiz_id = raiz_de(wordpress_id)
        categoria = categorias_raiz.get(raiz_id)
        if categoria is None:
            continue
        subcategoria = db.scalar(select(Subcategoria).where(Subcategoria.wordpress_id == wordpress_id))
        if subcategoria is None:
            subcategoria = Subcategoria(categoria_id=categoria.id, nombre=datos.get("name") or f"Subcategoría {wordpress_id}", slug="temporal", activo=True)
            db.add(subcategoria); db.flush()
        subcategoria.wordpress_id = wordpress_id
        subcategoria.categoria_id = categoria.id
        subcategoria.nombre = datos.get("name") or subcategoria.nombre
        subcategoria.slug = _slug_unico(db, Subcategoria, datos.get("slug") or subcategoria.nombre, wordpress_id, subcategoria.id)
        subcategoria.descripcion = datos.get("description") or None
        subcategoria.activo = True
        subcategorias[wordpress_id] = subcategoria
    db.flush()

    filas_productos = list(db.scalars(select(MigracionWooCommerce).where(MigracionWooCommerce.tipo == "producto")).all())
    resultado = {"procesados": 0, "creados": 0, "actualizados": 0, "publicados": 0, "variaciones": 0, "imagenes": 0}
    for fila in filas_productos:
        datos = fila.datos
        wordpress_id = int(datos["id"])
        producto = db.scalar(select(Producto).where(Producto.wordpress_id == wordpress_id))
        creado = producto is None
        if creado:
            producto = Producto(
                wordpress_id=wordpress_id, origen="wordpress", dux_codigo=f"WP-{wordpress_id}",
                nombre=datos.get("name") or f"Producto {wordpress_id}", slug="temporal",
            )
            db.add(producto); db.flush()
        vinculado_dux = (
            not creado
            and producto.conciliacion_estado == "vinculado"
            and not producto.dux_codigo.startswith("WP-")
        )
        producto.origen = "wordpress_dux" if vinculado_dux else "wordpress"
        producto.nombre = datos.get("name") or producto.nombre
        producto.slug = _slug_unico(db, Producto, datos.get("slug") or producto.nombre, wordpress_id, producto.id)
        producto.codigo_externo = (datos.get("sku") or "").strip() or None
        producto.descripcion = datos.get("description") or datos.get("short_description") or None
        fecha_alta_wordpress = _fecha(datos.get("date_created_gmt") or datos.get("date_created"))
        if fecha_alta_wordpress is not None:
            producto.creado_en = fecha_alta_wordpress
        publicado = datos.get("status") == "publish"
        producto.habilitado = publicado
        producto.visible_tienda = publicado

        ids_categorias = [int(item["id"]) for item in datos.get("categories") or [] if item.get("id")]
        id_especifica = next((item for item in ids_categorias if item in subcategorias), None)
        if id_especifica:
            producto.subcategoria = subcategorias[id_especifica]
            producto.categoria = subcategorias[id_especifica].categoria
        else:
            id_raiz = next((item for item in ids_categorias if item in categorias_raiz), None)
            producto.categoria = categorias_raiz.get(id_raiz) if id_raiz else None
            producto.subcategoria = None

        # La conversión puede repetirse sobre el mismo catálogo. Primero se
        # eliminan y confirman las relaciones que tienen claves únicas; de lo
        # contrario algunos motores intentan insertar antes de borrar.
        if not vinculado_dux:
            producto.precios.clear()
            producto.stocks.clear()
            producto.stocks_talles.clear()
        producto.variaciones.clear()
        producto.imagenes.clear()
        db.flush()

        variaciones = datos.get("_variaciones_completas") or []
        precios = [precio for precio in (_decimal(item.get("price")) for item in variaciones) if precio and precio > 0]
        precio = _decimal(datos.get("price")) or (min(precios) if precios else None)
        ids_listas = dict.fromkeys((
            settings.DUX_LISTA_PRECIO_MAYORISTA_ID,
            settings.DUX_LISTA_PRECIO_24_ID,
        ))
        if not vinculado_dux:
            producto.precios = [] if precio is None else [
                PrecioProducto(dux_id_lista=id_lista, nombre_lista="WordPress temporal", precio=precio)
                for id_lista in ids_listas
            ]

        stock_total = sum(int(item.get("stock_quantity") or 0) for item in variaciones)
        if not variaciones:
            stock_total = int(datos.get("stock_quantity") or 0)
        if not vinculado_dux:
            producto.stocks = [StockProducto(
                dux_id_deposito=-1, nombre_deposito="WordPress temporal", stock_real=stock_total,
                stock_reservado=0, stock_disponible=stock_total,
            )]

        stock_por_talle: dict[str, int] = {}
        producto.variaciones = []
        for variacion in variaciones:
            talle = _talle(variacion)
            if talle:
                talle = talle.strip()
                stock_por_talle[talle] = stock_por_talle.get(talle, 0) + int(variacion.get("stock_quantity") or 0)
            producto.variaciones.append(VariacionProducto(
                wordpress_id=int(variacion["id"]), sku=(variacion.get("sku") or "").strip() or None,
                atributos=_atributos(variacion), precio=_decimal(variacion.get("price")),
                stock=int(variacion.get("stock_quantity") or 0), estado_stock=variacion.get("stock_status"),
                habilitada=variacion.get("status", "publish") == "publish",
            ))
        if not vinculado_dux:
            producto.stocks_talles = [
                StockTalleProducto(talle=talle, cantidad=cantidad, origen="wordpress")
                for talle, cantidad in sorted(stock_por_talle.items())
            ]

        imagenes = datos.get("images") or []
        producto.imagen_url = imagenes[0].get("src") if imagenes else None
        producto.imagenes = [
            ImagenProducto(url=imagen["src"], orden=orden, principal=orden == 0)
            for orden, imagen in enumerate(imagenes) if imagen.get("src")
        ]
        db.flush()
        resultado["procesados"] += 1
        resultado["creados" if creado else "actualizados"] += 1
        resultado["publicados"] += int(publicado)
        resultado["variaciones"] += len(variaciones)
        resultado["imagenes"] += len(producto.imagenes)
        if progreso and resultado["procesados"] % 50 == 0:
            progreso(resultado.copy())
    db.commit()
    resultado["categorias"] = len(categorias_raiz)
    resultado["subcategorias"] = len(subcategorias)
    return resultado
