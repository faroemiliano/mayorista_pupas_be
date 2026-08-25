from app.database.session import SessionLocal
from app.integrations.dux.client import DuxClient
from app.services.dux_sync_service import (
    sincronizar_producto_desde_dux,
)


def main() -> None:
    dux = DuxClient()
    db = SessionLocal()

    try:
        respuesta = dux.get(
            "v2/items",
            params={
                "id_empresa": dux.id_empresa,
                "limit": 20,
                "offset": 0,
            },
        )

        productos = respuesta.get(
            "datos",
            [],
        )

        print("=" * 70)
        print("PRUEBA SINCRONIZACIÓN 20 PRODUCTOS")
        print("=" * 70)
        print("Productos recibidos:", len(productos))
        print("=" * 70)

        for posicion, producto_dux in enumerate(
            productos,
            start=1,
        ):
            producto = sincronizar_producto_desde_dux(
                db,
                producto_dux,
            )

            print(
                f"[{posicion}/{len(productos)}] "
                f"{producto.dux_codigo} | "
                f"{producto.nombre}"
            )

        db.commit()

        print()
        print("✅ PRUEBA CONFIRMADA EN POSTGRESQL")

    except Exception:
        db.rollback()
        raise

    finally:
        db.close()


if __name__ == "__main__":
    main()