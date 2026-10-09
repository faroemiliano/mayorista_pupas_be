from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.producto import Producto

from app.services.categoria_service import (
    get_categorias_service,
)
from app.services.marca_service import (
    get_marcas_service,
)


# =========================================================
# FILTROS PÚBLICOS DEL CATÁLOGO
# =========================================================

def get_catalogo_filtros_service(
    db: Session,
) -> dict:

    categorias = get_categorias_service(db=db, solo_activas=True)
    subcategorias_con_productos = set(db.scalars(
        select(Producto.subcategoria_id)
        .where(
            Producto.habilitado.is_(True),
            Producto.visible_tienda.is_(True),
            Producto.subcategoria_id.is_not(None),
        )
        .distinct()
    ).all())

    return {
        "categorias": [
            {
                "id": categoria.id,
                "dux_id": categoria.dux_id,
                "nombre": categoria.nombre,
                "slug": categoria.slug,
                "descripcion": categoria.descripcion,
                "activo": categoria.activo,
                "subcategorias": [
                    subcategoria
                    for subcategoria in categoria.subcategorias
                    if subcategoria.id in subcategorias_con_productos
                ],
            }
            for categoria in categorias
        ],
        "marcas": get_marcas_service(
            db=db,
            solo_activas=True,
        ),
    }
