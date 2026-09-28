import argparse

from app.database.session import SessionLocal
from app.services.conciliacion_productos_service import generar_conciliacion


def main() -> None:
    parser = argparse.ArgumentParser(description="Compara el staging de WordPress contra Dux sin modificar sistemas.")
    parser.add_argument("--confirmar-solo-lectura", action="store_true")
    args = parser.parse_args()
    if not args.confirmar_solo_lectura:
        parser.error("Usá --confirmar-solo-lectura para iniciar la comparación.")

    with SessionLocal() as db:
        resultado = generar_conciliacion(
            db,
            progreso=lambda procesados, total: print(f"Dux: {procesados}/{total} productos leídos", flush=True),
        )
    print(f"Conciliación finalizada: {resultado['totales']}", flush=True)


if __name__ == "__main__":
    main()
