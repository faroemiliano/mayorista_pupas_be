from datetime import datetime, timezone

from sqlalchemy import select, update

from app.database.session import SessionLocal
from app.models.categoria import Categoria
from app.models.migracion_woocommerce import MigracionWooCommerce
from app.models.producto import Producto
from app.models.subcategoria import Subcategoria
from app.services.conversion_catalogo_wordpress_service import convertir_catalogo_wordpress
from app.services.conversion_clientes_wordpress_service import convertir_clientes_wordpress
from app.services.conversion_pedidos_wordpress_service import convertir_pedidos_wordpress
from app.services.migracion_woocommerce_service import (
    _guardar,
    importar_todas_categorias,
    importar_todos_clientes_y_pedidos,
    importar_todos_productos,
)


TIPO_ESTADO = "estado_migracion"
ID_ESTADO = "wordpress-produccion"


def _estado(db, **cambios) -> dict:
    fila = db.scalar(select(MigracionWooCommerce).where(
        MigracionWooCommerce.tipo == TIPO_ESTADO,
        MigracionWooCommerce.id_externo == ID_ESTADO,
    ))
    datos = dict(fila.datos) if fila else {}
    datos.update(cambios)
    _guardar(db, TIPO_ESTADO, ID_ESTADO, datos)
    return datos


def obtener_estado_migracion(db) -> dict:
    fila = db.scalar(select(MigracionWooCommerce).where(
        MigracionWooCommerce.tipo == TIPO_ESTADO,
        MigracionWooCommerce.id_externo == ID_ESTADO,
    ))
    return fila.datos if fila else {"estado": "pendiente", "etapa": None, "resultado": None, "error": None}


def preparar_migracion_wordpress(db) -> dict:
    actual = obtener_estado_migracion(db)
    if actual.get("estado") == "en_progreso":
        raise ValueError("La migración de WordPress ya está en progreso.")
    return _estado(
        db, estado="en_progreso", etapa="preparando", progreso=None, resultado=None, error=None,
        iniciada_en=datetime.now(timezone.utc).isoformat(), finalizada_en=None,
    )


def _activar_catalogo_wordpress(db) -> int:
    resultado = db.execute(
        update(Producto)
        .where(Producto.wordpress_id.is_(None), Producto.origen == "dux")
        .values(habilitado=False, visible_tienda=False)
    )
    db.execute(update(Categoria).where(Categoria.wordpress_id.is_(None)).values(activo=False))
    db.execute(update(Subcategoria).where(Subcategoria.wordpress_id.is_(None)).values(activo=False))
    db.commit()
    return max(resultado.rowcount or 0, 0)


def ejecutar_migracion_wordpress_background() -> None:
    with SessionLocal() as db:
        try:
            _estado(db, etapa="categorias", progreso=None)
            categorias = importar_todas_categorias(db)

            _estado(db, etapa="productos", progreso={"procesados": 0})
            productos = importar_todos_productos(
                db,
                progreso=lambda _pagina, _paginas, _producto, total: (
                    _estado(db, progreso=total) if total["procesados"] % 50 == 0 else None
                ),
            )

            _estado(db, etapa="clientes_y_pedidos", progreso={"procesados": 0})
            staging = importar_todos_clientes_y_pedidos(
                db,
                progreso=lambda tipo, pagina, paginas, total: _estado(
                    db, progreso={"tipo": tipo, "pagina": pagina, "paginas": paginas, **total}
                ),
            )

            _estado(db, etapa="convirtiendo_catalogo", progreso={"procesados": 0})
            catalogo = convertir_catalogo_wordpress(
                db, progreso=lambda total: _estado(db, progreso=total)
            )
            _estado(db, etapa="convirtiendo_clientes", progreso={"procesados": 0})
            clientes = convertir_clientes_wordpress(
                db, progreso=lambda total: _estado(db, progreso=total)
            )
            _estado(db, etapa="convirtiendo_pedidos", progreso={"procesados": 0})
            pedidos = convertir_pedidos_wordpress(
                db, progreso=lambda total: _estado(db, progreso=total)
            )
            archivados = _activar_catalogo_wordpress(db)
            resultado = {
                "categorias": categorias, "productos_staging": productos, "staging": staging,
                "catalogo": catalogo, "clientes": clientes, "pedidos": pedidos,
                "productos_dux_ocultados": archivados,
            }
            _estado(
                db, estado="completada", etapa="finalizada", progreso=None, resultado=resultado,
                error=None, finalizada_en=datetime.now(timezone.utc).isoformat(),
            )
        except Exception as error:
            db.rollback()
            _estado(
                db, estado="error", etapa="error", error=str(error),
                finalizada_en=datetime.now(timezone.utc).isoformat(),
            )
            raise
