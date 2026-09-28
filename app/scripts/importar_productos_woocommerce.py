import argparse

from app.database.session import SessionLocal
from app.services.migracion_woocommerce_service import importar_todos_productos


def main() -> None:
    parser = argparse.ArgumentParser(description="Copia productos y variaciones de WooCommerce al staging local.")
    parser.add_argument("--confirmar-solo-lectura", action="store_true")
    args = parser.parse_args()
    if not args.confirmar_solo_lectura:
        parser.error("Usá --confirmar-solo-lectura para iniciar la copia.")

    def mostrar(pagina: int, paginas: int, producto: dict, total: dict) -> None:
        print(
            f"productos: página {pagina}/{paginas} · {total['procesados']} procesados · "
            f"{total['creados']} nuevos · {total['actualizados']} actualizados · "
            f"{total['sin_cambios']} sin cambios · último #{producto['id']}",
            flush=True,
        )

    with SessionLocal() as db:
        resultado = importar_todos_productos(db, progreso=mostrar)
    print(f"Copia de productos finalizada: {resultado}", flush=True)


if __name__ == "__main__":
    main()
