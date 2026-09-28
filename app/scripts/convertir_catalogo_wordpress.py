import argparse

from app.database.session import SessionLocal
from app.services.conversion_catalogo_wordpress_service import convertir_catalogo_wordpress
from app.services.migracion_woocommerce_service import importar_todas_categorias


def main() -> None:
    parser = argparse.ArgumentParser(description="Convierte el staging de WordPress en catálogo local.")
    parser.add_argument("--confirmar-local", action="store_true")
    args = parser.parse_args()
    if not args.confirmar_local:
        parser.error("Usá --confirmar-local para iniciar la conversión.")
    with SessionLocal() as db:
        categorias = importar_todas_categorias(db)
        print(f"Categorías copiadas: {categorias}", flush=True)
        resultado = convertir_catalogo_wordpress(db, progreso=lambda total: print(f"Catálogo: {total['procesados']} productos convertidos", flush=True))
    print(f"Conversión finalizada: {resultado}", flush=True)


if __name__ == "__main__":
    main()
