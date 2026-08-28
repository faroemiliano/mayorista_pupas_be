import sys

from app.database.session import SessionLocal
from app.repositories.usuario_repository import get_usuario_by_email


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("Uso: python -m app.scripts.hacer_admin correo@gmail.com")
    email = sys.argv[1].strip().lower()
    with SessionLocal() as db:
        usuario = get_usuario_by_email(db, email)
        if usuario is None:
            raise SystemExit("Ese correo todavía no inició sesión con Google en la tienda.")
        usuario.rol = "admin"
        db.commit()
        print(f"Administrador habilitado: {email}")


if __name__ == "__main__":
    main()
