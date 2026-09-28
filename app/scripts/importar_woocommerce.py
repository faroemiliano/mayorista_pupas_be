import argparse

from app.database.session import SessionLocal
from app.services.migracion_woocommerce_service import importar_todos_clientes_y_pedidos


def main() -> None:
    parser = argparse.ArgumentParser(description="Copia clientes y pedidos de WooCommerce al staging local.")
    parser.add_argument("--confirmar-solo-lectura", action="store_true", help="Confirma que sólo se leerá WooCommerce.")
    args = parser.parse_args()
    if not args.confirmar_solo_lectura:
        parser.error("Usá --confirmar-solo-lectura para iniciar la copia.")

    def mostrar(tipo: str, pagina: int, paginas: int, total: dict) -> None:
        print(
            f"{tipo}: página {pagina}/{paginas} · {total['procesados']} procesados · "
            f"{total['creados']} nuevos · {total['actualizados']} actualizados · "
            f"{total['sin_cambios']} sin cambios",
            flush=True,
        )

    with SessionLocal() as db:
        resultado = importar_todos_clientes_y_pedidos(db, progreso=mostrar)
    print(f"Copia finalizada: {resultado}", flush=True)


if __name__ == "__main__":
    main()
