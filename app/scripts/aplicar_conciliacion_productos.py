import argparse

from app.database.session import SessionLocal
from app.services.conciliacion_productos_service import aplicar_coincidencias_seguras


def main() -> None:
    parser = argparse.ArgumentParser(description="Vincula localmente coincidencias seguras entre WordPress y Dux.")
    parser.add_argument("--confirmar-local", action="store_true")
    args = parser.parse_args()
    if not args.confirmar_local:
        parser.error("Usá --confirmar-local para aplicar únicamente en la base configurada.")
    with SessionLocal() as db:
        resultado = aplicar_coincidencias_seguras(db)
    print(f"Conciliación aplicada: {resultado}")


if __name__ == "__main__":
    main()
