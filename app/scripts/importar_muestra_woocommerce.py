import argparse

from app.database.session import SessionLocal
from app.services.migracion_woocommerce_service import importar_muestra


def main() -> None:
    parser = argparse.ArgumentParser(description="Importa una muestra de WooCommerce a staging.")
    parser.add_argument("--producto-id", type=int, required=True)
    parser.add_argument("--cliente-email", required=True)
    parser.add_argument("--pedido-id", type=int, required=True)
    args = parser.parse_args()
    with SessionLocal() as db:
        resultados = importar_muestra(db, producto_id=args.producto_id, cliente_email=args.cliente_email, pedido_id=args.pedido_id)
        resumen = [(fila.tipo, fila.id_externo, fila.checksum, creada) for fila, creada in resultados]
    for tipo, id_externo, checksum, creada in resumen:
        print(f"{tipo} {id_externo}: {'creado' if creada else 'actualizado/verificado'} ({checksum[:12]})")


if __name__ == "__main__":
    main()
