import argparse

from app.database.session import SessionLocal
from app.services.conversion_pedidos_wordpress_service import convertir_pedidos_wordpress


def main() -> None:
    parser = argparse.ArgumentParser(description="Convierte pedidos WordPress en historial local.")
    parser.add_argument("--confirmar-local", action="store_true")
    args = parser.parse_args()
    if not args.confirmar_local:
        parser.error("Usá --confirmar-local para iniciar la conversión.")
    with SessionLocal() as db:
        resultado = convertir_pedidos_wordpress(
            db, progreso=lambda total: print(f"Pedidos: {total['procesados']} · items: {total['items']}", flush=True)
        )
    print(f"Conversión finalizada: {resultado}", flush=True)


if __name__ == "__main__":
    main()
