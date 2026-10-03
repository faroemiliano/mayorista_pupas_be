from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select, update

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
from app.services.migracion_imagenes_cloudinary_service import (
    _configurar_cloudinary,
    migrar_imagenes_a_cloudinary,
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
    if not fila:
        return {"estado": "pendiente", "etapa": None, "resultado": None, "error": None, "actualizado_en": None}
    datos = dict(fila.datos)
    datos["actualizado_en"] = fila.actualizado_en.isoformat() if fila.actualizado_en else None
    return datos


def preparar_migracion_wordpress(db) -> dict:
    actual = obtener_estado_migracion(db)
    if actual.get("estado") == "en_progreso":
        fila = db.scalar(select(MigracionWooCommerce).where(
            MigracionWooCommerce.tipo == TIPO_ESTADO,
            MigracionWooCommerce.id_externo == ID_ESTADO,
        ))
        actualizado = fila.actualizado_en if fila else None
        if actualizado and actualizado.tzinfo is None:
            actualizado = actualizado.replace(tzinfo=timezone.utc)
        if actualizado and datetime.now(timezone.utc) - actualizado < timedelta(minutes=2):
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


def ejecutar_migracion_wordpress_background(actualizar_todo: bool = False) -> None:
    with SessionLocal() as db:
        try:
            def cantidad(tipo: str) -> int:
                return db.scalar(select(func.count(MigracionWooCommerce.id)).where(MigracionWooCommerce.tipo == tipo)) or 0

            _estado(db, etapa="validando_cloudinary", progreso=None)
            _configurar_cloudinary()

            _estado(db, etapa="categorias", progreso=None)
            categorias = {"omitido": True, "existentes": cantidad("categoria")} if not actualizar_todo and cantidad("categoria") >= 10 else importar_todas_categorias(db)

            _estado(db, etapa="productos", progreso={"procesados": 0})
            productos = {"omitido": True, "existentes": cantidad("producto")} if not actualizar_todo and cantidad("producto") >= 500 else importar_todos_productos(
                db,
                progreso=lambda _pagina, _paginas, _producto, total: (
                    _estado(db, progreso=total) if total["procesados"] % 50 == 0 else None
                ),
            )

            _estado(db, etapa="clientes_y_pedidos", progreso={"procesados": 0})
            staging = {"omitido": True, "clientes": cantidad("cliente"), "pedidos": cantidad("pedido")} if not actualizar_todo and cantidad("cliente") >= 5000 and cantidad("pedido") >= 10000 else importar_todos_clientes_y_pedidos(
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
            _estado(db, etapa="copiando_imagenes_cloudinary", progreso={"procesadas": 0})
            imagenes = migrar_imagenes_a_cloudinary(
                db, progreso=lambda total: _estado(db, progreso=total)
            )
            archivados = _activar_catalogo_wordpress(db)
            resultado = {
                "actualizacion_completa": actualizar_todo,
                "categorias": categorias, "productos_staging": productos, "staging": staging,
                "catalogo": catalogo, "clientes": clientes, "pedidos": pedidos,
                "imagenes_cloudinary": imagenes,
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
