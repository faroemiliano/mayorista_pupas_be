from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models.producto import Producto


# =========================================================
# OBTENER PRODUCTOS PARA CALCULAR EL CARRITO
# =========================================================

def get_productos_carrito(
    db: Session,
    producto_ids: set[int],
) -> list[Producto]:

    if not producto_ids:
        return []

    query = (
        select(Producto)
        .options(
            selectinload(
                Producto.precios
            ),
            selectinload(
                Producto.stocks
            ),
            selectinload(
                Producto.imagenes
            ),
        )
        .where(
            Producto.id.in_(producto_ids),
            Producto.habilitado.is_(True),
        )
    )

    return list(
        db.scalars(query).all()
    )
