import time
from app.integrations.dux.client import DuxClient
from slugify import slugify
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.models.categoria import Categoria

from datetime import date

from app.models.producto import Producto
from app.models.precio_producto import PrecioProducto
from app.models.stock_producto import StockProducto
from app.models.imagen_producto import ImagenProducto
from app.models.codigo_barra_producto import CodigoBarraProducto


def obtener_o_crear_categoria_desde_dux(
    db: Session,
    rubro: dict | None,
) -> Categoria | None:

    if rubro is None:
        return None

    dux_id = rubro.get("id")
    nombre = rubro.get("nombre")

    if not dux_id or not nombre:
        return None

    categoria = db.scalar(
        select(Categoria).where(
            Categoria.dux_id == dux_id
        )
    )

    if categoria is not None:
        categoria.nombre = nombre
        categoria.activo = True
        return categoria

    categoria = db.scalar(
        select(Categoria).where(
            Categoria.nombre == nombre
        )
    )

    if categoria is not None:
        categoria.dux_id = dux_id
        categoria.activo = True
        return categoria

    slug_base = slugify(nombre)

    slug = slug_base
    contador = 2

    while db.scalar(
        select(Categoria).where(
            Categoria.slug == slug
        )
    ) is not None:
        slug = f"{slug_base}-{contador}"
        contador += 1

    categoria = Categoria(
        dux_id=dux_id,
        nombre=nombre,
        slug=slug,
        activo=True,
    )

    db.add(categoria)
    db.flush()

    print(
        f"✅ Categoría creada: "
        f"{categoria.nombre} "
        f"(Dux ID: {categoria.dux_id})"
    )

    return categoria

from app.models.subcategoria import Subcategoria
from app.models.marca import Marca


def obtener_o_crear_subcategoria_desde_dux(
    db: Session,
    sub_rubro: dict | None,
    categoria: Categoria | None,
) -> Subcategoria | None:

    if sub_rubro is None:
        return None

    if categoria is None:
        return None

    dux_id = sub_rubro.get("id")
    nombre = sub_rubro.get("nombre")

    if not dux_id or not nombre:
        return None

    subcategoria = db.scalar(
        select(Subcategoria).where(
            Subcategoria.dux_id == dux_id
        )
    )

    if subcategoria is not None:
        subcategoria.nombre = nombre
        subcategoria.categoria_id = categoria.id
        subcategoria.activo = True
        return subcategoria

    subcategoria = db.scalar(
        select(Subcategoria).where(
            Subcategoria.categoria_id == categoria.id,
            Subcategoria.nombre == nombre,
        )
    )

    if subcategoria is not None:
        subcategoria.dux_id = dux_id
        subcategoria.activo = True
        return subcategoria

    slug_base = slugify(
        f"{categoria.nombre}-{nombre}"
    )

    slug = slug_base
    contador = 2

    while db.scalar(
        select(Subcategoria).where(
            Subcategoria.slug == slug
        )
    ) is not None:

        slug = f"{slug_base}-{contador}"
        contador += 1

    subcategoria = Subcategoria(
        dux_id=dux_id,
        categoria_id=categoria.id,
        nombre=nombre,
        slug=slug,
        activo=True,
    )

    db.add(subcategoria)
    db.flush()

    print(
        f"✅ Subcategoría creada: "
        f"{subcategoria.nombre} "
        f"(Dux ID: {subcategoria.dux_id})"
    )

    return subcategoria


def obtener_o_crear_marca_desde_dux(
    db: Session,
    marca_dux: dict | None,
) -> Marca | None:

    if marca_dux is None:
        return None

    dux_id = marca_dux.get("id")
    nombre = marca_dux.get("nombre")

    if not nombre:
        return None

    if dux_id is not None:

        marca = db.scalar(
            select(Marca).where(
                Marca.dux_id == dux_id
            )
        )

        if marca is not None:
            marca.nombre = nombre
            marca.activo = True
            return marca

    marca = db.scalar(
        select(Marca).where(
            Marca.nombre == nombre
        )
    )

    if marca is not None:
        marca.dux_id = dux_id
        marca.activo = True
        return marca

    slug_base = slugify(nombre)

    slug = slug_base
    contador = 2

    while db.scalar(
        select(Marca).where(
            Marca.slug == slug
        )
    ) is not None:

        slug = f"{slug_base}-{contador}"
        contador += 1

    marca = Marca(
        dux_id=dux_id,
        nombre=nombre,
        slug=slug,
        activo=True,
    )

    db.add(marca)
    db.flush()

    print(
        f"✅ Marca creada: "
        f"{marca.nombre} "
        f"(Dux ID: {marca.dux_id})"
    )

    return marca

def sincronizar_producto_desde_dux(
    db: Session,
    producto_dux: dict,
) -> Producto:

    codigo_dux = producto_dux.get(
        "cod_item"
    )

    dux_codigo = (
        str(codigo_dux).strip()
        if codigo_dux is not None
        else ""
    )

    nombre = (
        producto_dux.get("item") or ""
    ).strip()

    if not dux_codigo:
        raise ValueError(
            "Producto Dux sin cod_item."
        )

    if not nombre:
        raise ValueError(
            f"Producto {dux_codigo} sin nombre."
        )

    # =====================================================
    # CATEGORÍA / SUBCATEGORÍA / MARCA
    # =====================================================

    categoria = obtener_o_crear_categoria_desde_dux(
        db,
        producto_dux.get("rubro"),
    )

    subcategoria = obtener_o_crear_subcategoria_desde_dux(
        db,
        producto_dux.get("sub_rubro"),
        categoria,
    )

    marca = obtener_o_crear_marca_desde_dux(
        db,
        producto_dux.get("marca"),
    )

    # =====================================================
    # BUSCAR PRODUCTO EXISTENTE
    # =====================================================

    producto = db.scalar(
        select(Producto).where(
            Producto.dux_codigo == dux_codigo
        )
    )

    # =====================================================
    # SLUG
    # =====================================================

    slug_base = slugify(
        f"{nombre}-{dux_codigo}"
    )

    if producto is None:

        slug = slug_base
        contador = 2

        while db.scalar(
            select(Producto).where(
                Producto.slug == slug
            )
        ) is not None:

            slug = f"{slug_base}-{contador}"
            contador += 1

        producto = Producto(
            dux_codigo=dux_codigo,
            nombre=nombre,
            slug=slug,
        )

        db.add(producto)
        db.flush()

        print(
            f"✅ Producto creado: "
            f"{producto.nombre} "
            f"({producto.dux_codigo})"
        )

    else:

        print(
            f"🔄 Producto actualizado: "
            f"{producto.nombre} "
            f"({producto.dux_codigo})"
        )

    # =====================================================
    # DATOS GENERALES
    # =====================================================

    producto.nombre = nombre

    producto.codigo_externo = (
        producto_dux.get("codigo_externo")
        or None
    )

    # Dux no incluye actualmente la descripción en el
    # payload de items. Si la agrega, la sincronizamos sin
    # borrar contenido local cuando la clave no está.
    if "descripcion" in producto_dux:
        producto.descripcion = (
            producto_dux.get("descripcion")
            or None
        )

    producto.costo = (
        producto_dux.get("costo")
    )

    producto.porcentaje_iva = (
        producto_dux.get("porc_iva")
    )

    producto.imagen_url = (
        producto_dux.get("imagen_url")
        or None
    )

    producto.cantidad_unidades_por_bulto = (
        producto_dux.get(
            "ctd_unidades_por_bulto"
        )
    )

    producto.habilitado = bool(
        producto_dux.get(
            "habilitado",
            True,
        )
    )

    fecha_creacion = producto_dux.get(
        "fecha_creacion"
    )

    if fecha_creacion:
        producto.fecha_creacion_dux = date.fromisoformat(
            fecha_creacion
        )
    else:
        producto.fecha_creacion_dux = None

    producto.categoria_id = (
        categoria.id
        if categoria
        else None
    )

    producto.subcategoria_id = (
        subcategoria.id
        if subcategoria
        else None
    )

    producto.marca_id = (
        marca.id
        if marca
        else None
    )

    # =====================================================
    # LIMPIAR RELACIONES ANTERIORES
    # =====================================================

    producto.precios.clear()
    producto.stocks.clear()
    producto.codigos_barra.clear()
    producto.imagenes.clear()

    # Ejecutamos los DELETE antes de insertar
    # nuevamente los datos sincronizados.
    db.flush()

    # =====================================================
    # PRECIOS
    # =====================================================

    for precio_dux in (
        producto_dux.get("precios")
        or []
    ):

        precio = PrecioProducto(
            dux_id_lista=precio_dux["id"],
            nombre_lista=precio_dux["nombre"],
            precio=precio_dux.get(
                "precio",
                0,
            ),
        )

        producto.precios.append(
            precio
        )

    # =====================================================
    # STOCK
    # =====================================================

    for stock_dux in (
        producto_dux.get("stock")
        or []
    ):

        stock = StockProducto(
            dux_id_deposito=stock_dux["id"],
            nombre_deposito=stock_dux["nombre"],
            stock_real=stock_dux.get(
                "stock_real",
                0,
            ),
            stock_reservado=stock_dux.get(
                "stock_reservado",
                0,
            ),
            stock_disponible=stock_dux.get(
                "stock_disponible",
                0,
            ),
            dux_id_det_item=stock_dux.get(
                "id_det_item"
            ),
            codigo_barra_detalle=stock_dux.get(
                "cod_barra_detalle"
            ),
            talle=stock_dux.get(
                "talle"
            ),
            color=stock_dux.get(
                "color"
            ),
        )

        producto.stocks.append(
            stock
        )

    # =====================================================
    # CÓDIGOS DE BARRA
    # =====================================================

    for codigo in (
        producto_dux.get("codigos_barra")
        or []
    ):

        if not codigo:
            continue

        producto.codigos_barra.append(
            CodigoBarraProducto(
                codigo=str(codigo).strip(),
            )
        )

    # =====================================================
    # IMAGEN
    # =====================================================

    imagen_url = producto_dux.get(
        "imagen_url"
    )

    if imagen_url:

        producto.imagenes.append(
            ImagenProducto(
                url=imagen_url,
                orden=0,
                principal=True,
            )
        )

    # =====================================================
    # FLUSH FINAL
    # =====================================================

    db.flush()

    return producto


def sincronizar_catalogo_dux(
    db: Session,
) -> dict:

    dux = DuxClient()

    limit = 20
    offset = 0

    procesados = 0
    errores = 0
    codigos_sincronizados: set[str] = set()

    # Las categorías, subcategorías y marcas disponibles se
    # reconstruyen a partir del catálogo completo recibido.
    db.execute(
        update(Categoria).values(
            activo=False
        )
    )
    db.execute(
        update(Subcategoria).values(
            activo=False
        )
    )
    db.execute(
        update(Marca).values(
            activo=False
        )
    )

    while True:

        print()
        print(
            f"📦 Consultando Dux "
            f"offset={offset} limit={limit}"
        )

        respuesta = dux.get(
            "v2/items",
            params={
                "id_empresa": dux.id_empresa,
                "limit": limit,
                "offset": offset,
            },
        )

        productos_dux = respuesta.get(
            "datos",
            [],
        )

        paginacion = respuesta.get(
            "paginacion",
            {},
        )

        if not productos_dux:
            break

        for producto_dux in productos_dux:

            codigo = producto_dux.get(
                "cod_item"
            )

            nombre = producto_dux.get(
                "item"
            )

            try:

                sincronizar_producto_desde_dux(
                    db,
                    producto_dux,
                )

                procesados += 1

                codigo_sincronizado = producto_dux.get(
                    "cod_item"
                )

                if codigo_sincronizado is not None:
                    codigos_sincronizados.add(
                        str(codigo_sincronizado).strip()
                    )

            except Exception as error:

                errores += 1

                print(
                    f"❌ Error producto "
                    f"{codigo} - {nombre}: "
                    f"{error}"
                )

                raise

        # Enviamos los cambios de la página a PostgreSQL sin
        # confirmarlos todavía. El catálogo se confirma como
        # una única operación al finalizar todas las páginas.
        db.flush()

        print(
            f"✅ Página procesada | "
            f"Procesados: {procesados}"
        )

        if not paginacion.get(
            "hay_mas",
            False,
        ):
            break

        offset += limit

        # Evitamos bombardear la API.
        time.sleep(1)

    if not codigos_sincronizados:
        raise RuntimeError(
            "Dux devolvió un catálogo vacío; se cancela "
            "la sincronización para no deshabilitar todos "
            "los productos locales."
        )

    # Un producto local que ya no aparece en el catálogo
    # completo de Dux deja de publicarse, pero se conserva su
    # historial en la base de datos.
    productos_ausentes_query = update(
        Producto
    ).values(
        habilitado=False
    )

    productos_ausentes_query = (
        productos_ausentes_query.where(
            Producto.dux_codigo.not_in(
                codigos_sincronizados
            )
        )
    )

    resultado_ausentes = db.execute(
        productos_ausentes_query
    )

    filas_ausentes = resultado_ausentes.rowcount

    deshabilitados_ausentes = max(
        filas_ausentes or 0,
        0,
    )

    # Si cualquier página falla, esta confirmación no se
    # alcanza y el caller revierte toda la sincronización.
    db.commit()

    return {
        "procesados": procesados,
        "errores": errores,
        "offset_final": offset,
        "deshabilitados_ausentes": (
            deshabilitados_ausentes
        ),
    }
