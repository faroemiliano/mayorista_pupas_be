import argparse

from app.database.session import SessionLocal
from app.services.woocommerce_cliente_service import importar_cliente_woocommerce


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("email")
    args = parser.parse_args()
    with SessionLocal() as db:
        usuario, creado, password = importar_cliente_woocommerce(db, args.email)
    print(f"Cliente {'creado' if creado else 'actualizado'}: {usuario.email}")
    print(f"Nombre: {usuario.nombre} {usuario.apellido}".strip())
    if password:
        print(f"Contraseña temporal (se muestra una sola vez): {password}")


if __name__ == "__main__":
    main()
