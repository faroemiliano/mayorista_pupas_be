import argparse

from app.database.session import SessionLocal
from app.services.conversion_clientes_wordpress_service import convertir_clientes_wordpress


def main() -> None:
    parser = argparse.ArgumentParser(description="Convierte clientes WordPress en cuentas locales migradas.")
    parser.add_argument("--confirmar-local", action="store_true")
    args = parser.parse_args()
    if not args.confirmar_local:
        parser.error("Usá --confirmar-local para iniciar la conversión.")
    with SessionLocal() as db:
        resultado = convertir_clientes_wordpress(
            db, progreso=lambda total: print(f"Clientes: {total['procesados']} procesados", flush=True)
        )
    print(f"Conversión finalizada: {resultado}", flush=True)


if __name__ == "__main__":
    main()
