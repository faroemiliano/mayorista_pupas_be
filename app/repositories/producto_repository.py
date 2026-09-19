from sqlalchemy import (
    func,
    or_,
    select,
)
from sqlalchemy.orm import (
    Session,
    selectinload,
)

from app.models.categoria import Categoria
from app.models.marca import Marca
from app.models.imagen_producto import ImagenProducto
from app.models.producto import Producto
from app.models.stock_producto import StockProducto
from app.models.subcategoria import Subcategoria
from app.models.reserva_stock import ReservaStock


# =========================================================
# OBTENER URL DE IMAGEN POR ID DE PRODUCTO
# =========================================================

def get_producto_imagen_url(
    db: Session,
    producto_id: int,
) -> str | None:

    query = select(
        Producto.imagen_url
    ).where(
        Producto.id == producto_id,
        Producto.habilitado.is_(True),
    )

    return db.scalar(query)


def get_imagen_producto_url(
    db: Session,
    producto_id: int,
    imagen_id: int,
) -> str | None:
    """Obtiene una imagen que realmente pertenece al producto solicitado."""

    query = (
        select(ImagenProducto.url)
        .join(Producto, Producto.id == ImagenProducto.producto_id)
        .where(
            ImagenProducto.id == imagen_id,
            ImagenProducto.producto_id == producto_id,
            Producto.habilitado.is_(True),
            Producto.visible_tienda.is_(True),
        )
    )

    return db.scalar(query)


# =========================================================
# OBTENER PRODUCTO POR ID
# =========================================================

def get_producto(
    db: Session,
    producto_id: int,
) -> Producto | None:

    query = (
        select(Producto)
        .options(
            selectinload(
                Producto.categoria
            ),
            selectinload(
                Producto.subcategoria
            ),
            selectinload(
                Producto.marca
            ),
            selectinload(
                Producto.precios
            ),
            selectinload(
                Producto.stocks
            ),
            selectinload(Producto.stocks_talles),
            selectinload(
                Producto.imagenes
            ),
            selectinload(
                Producto.codigos_barra
            ),
        )
        .where(
            Producto.id == producto_id
        )
    )

    return db.scalar(query)


# =========================================================
# OBTENER PRODUCTO POR SLUG
# =========================================================

def get_producto_by_slug(
    db: Session,
    slug: str,
) -> Producto | None:

    query = (
        select(Producto)
        .options(
            selectinload(
                Producto.categoria
            ),
            selectinload(
                Producto.subcategoria
            ),
            selectinload(
                Producto.marca
            ),
            selectinload(
                Producto.precios
            ),
            selectinload(
                Producto.stocks
            ),
            selectinload(Producto.stocks_talles),
            selectinload(
                Producto.imagenes
            ),
            selectinload(
                Producto.codigos_barra
            ),
        )
        .where(
            Producto.slug == slug
        )
    )

    return db.scalar(query)


# =========================================================
# OBTENER PRODUCTO POR CÓDIGO DUX
# =========================================================

def get_producto_by_dux_codigo(
    db: Session,
    dux_codigo: str,
) -> Producto | None:

    query = (
        select(Producto)
        .where(
            Producto.dux_codigo
            == dux_codigo
        )
    )

    return db.scalar(query)


# =========================================================
# LISTAR PRODUCTOS
# =========================================================

def get_productos(
    db: Session,
    buscar: str | None = None,
    categoria_id: int | None = None,
    subcategoria_id: int | None = None,
    marca_id: int | None = None,
    solo_habilitados: bool = True,
    con_stock: bool | None = None,
    page: int = 1,
    limit: int = 20,
    orden: str = "nombre_asc",
) -> tuple[list[Producto], int]:

    # =====================================================
    # QUERY PRINCIPAL
    # =====================================================

    query = (
        select(Producto)
        .options(
            selectinload(
                Producto.categoria
            ),
            selectinload(
                Producto.subcategoria
            ),
            selectinload(
                Producto.marca
            ),
            selectinload(
                Producto.precios
            ),
            selectinload(
                Producto.stocks
            ),
            selectinload(Producto.stocks_talles),
            selectinload(
                Producto.imagenes
            ),
        )
    )

    # =====================================================
    # COUNT
    # =====================================================

    count_query = select(
        func.count(Producto.id)
    )

    # =====================================================
    # HABILITADOS
    # =====================================================

    if solo_habilitados:

        filtro = (
            Producto.habilitado.is_(True)
            & Producto.visible_tienda.is_(True)
        )

        query = query.where(
            filtro
        )

        count_query = (
            count_query.where(
                filtro
            )
        )

    # =====================================================
    # CATEGORÍA
    # =====================================================

    if categoria_id is not None:

        filtro = (
            Producto.categoria_id
            == categoria_id
        )

        query = query.where(
            filtro
        )

        count_query = (
            count_query.where(
                filtro
            )
        )

    # =====================================================
    # SUBCATEGORÍA
    # =====================================================

    if subcategoria_id is not None:

        filtro = (
            Producto.subcategoria_id
            == subcategoria_id
        )

        query = query.where(
            filtro
        )

        count_query = (
            count_query.where(
                filtro
            )
        )

    # =====================================================
    # MARCA
    # =====================================================

    if marca_id is not None:

        filtro = (
            Producto.marca_id
            == marca_id
        )

        query = query.where(
            filtro
        )

        count_query = (
            count_query.where(
                filtro
            )
        )

    # =====================================================
# STOCK
# =====================================================

    if con_stock is not None:
        stock_totales = (
            select(
                StockProducto.producto_id.label("producto_id"),
                func.sum(StockProducto.stock_disponible).label("cantidad"),
            )
            .group_by(StockProducto.producto_id)
            .subquery()
        )
        reservas_totales = (
            select(
                ReservaStock.producto_id.label("producto_id"),
                func.sum(ReservaStock.cantidad).label("cantidad"),
            )
            .where(ReservaStock.estado.in_(("activa", "enviada_dux")))
            .group_by(ReservaStock.producto_id)
            .subquery()
        )
        query = query.outerjoin(stock_totales, stock_totales.c.producto_id == Producto.id)
        query = query.outerjoin(reservas_totales, reservas_totales.c.producto_id == Producto.id)
        count_query = count_query.outerjoin(stock_totales, stock_totales.c.producto_id == Producto.id)
        count_query = count_query.outerjoin(reservas_totales, reservas_totales.c.producto_id == Producto.id)
        stock_efectivo = (
            func.coalesce(stock_totales.c.cantidad, 0)
            - func.coalesce(reservas_totales.c.cantidad, 0)
        )
        filtro = stock_efectivo > 0 if con_stock else stock_efectivo <= 0

        query = query.where(
            filtro
        )

        count_query = (
            count_query.where(
                filtro
            )
        )

    # =====================================================
    # BÚSQUEDA
    # =====================================================

    if buscar:

        termino = (
            f"%{buscar.strip()}%"
        )

        filtro_busqueda = or_(
            Producto.nombre.ilike(
                termino
            ),
            Producto.dux_codigo.ilike(
                termino
            ),
            Producto.codigo_externo.ilike(
                termino
            ),
            Producto.categoria.has(
                Categoria.nombre.ilike(
                    termino
                )
            ),
            Producto.subcategoria.has(
                Subcategoria.nombre.ilike(
                    termino
                )
            ),
            Producto.marca.has(
                Marca.nombre.ilike(
                    termino
                )
            ),
        )

        query = query.where(
            filtro_busqueda
        )

        count_query = (
            count_query.where(
                filtro_busqueda
            )
        )

    # =====================================================
    # ORDEN
    # =====================================================

    if orden == "nombre_desc":

        query = query.order_by(
            Producto.nombre.desc(),
            Producto.id.desc(),
        )

    elif orden == "recientes":

        query = query.order_by(
            Producto.fecha_creacion_dux.desc().nulls_last(),
            Producto.id.desc(),
        )

    elif orden == "antiguos":

        query = query.order_by(
            Producto.fecha_creacion_dux.asc().nulls_last(),
            Producto.id.asc(),
        )

    else:

        query = query.order_by(
            Producto.nombre.asc(),
            Producto.id.asc(),
        )

    # =====================================================
    # PAGINACIÓN
    # =====================================================

    offset = (
        page - 1
    ) * limit

    query = (
        query
        .offset(offset)
        .limit(limit)
    )

    # =====================================================
    # EJECUCIÓN
    # =====================================================

    productos = list(
        db.scalars(
            query
        ).all()
    )

    total = (
        db.scalar(
            count_query
        )
        or 0
    )

    return productos, total
