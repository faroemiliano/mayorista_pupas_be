from app.database.session import SessionLocal
from app.services.dux_sync_service import (
    sincronizar_catalogo_dux,
)


def main() -> None:

    db = SessionLocal()

    try:

        print("=" * 60)
        print("SINCRONIZACIÓN CATÁLOGO DUX")
        print("=" * 60)

        resultado = sincronizar_catalogo_dux(
            db,
        )

        print()
        print("=" * 60)
        print("SINCRONIZACIÓN FINALIZADA")
        print("=" * 60)

        print(
            "Productos procesados:",
            resultado["procesados"],
        )

        print(
            "Errores:",
            resultado["errores"],
        )

        print(
            "Deshabilitados por ausencia en Dux:",
            resultado[
                "deshabilitados_ausentes"
            ],
        )

    except Exception:

        db.rollback()
        raise

    finally:

        db.close()


if __name__ == "__main__":
    main()
