import sys

from app.database.session import SessionLocal
from app.repositories.usuario_repository import get_usuario_by_email


def main() -> None:
    if len(sys.argv) not in {2, 3} or (len(sys.argv) == 3 and sys.argv[2] != "operativo"):
        raise SystemExit("Uso: python -m app.scripts.hacer_admin correo@gmail.com [operativo]")
    email = sys.argv[1].strip().lower()
    with SessionLocal() as db:
        usuario = get_usuario_by_email(db, email)
        if usuario is None:
            raise SystemExit("Ese correo todavía no inició sesión con Google en la tienda.")
        usuario.rol = "admin_operativo" if len(sys.argv) == 3 else "admin"
        db.commit()
        print(f"Rol habilitado para {email}: {usuario.rol}")


if __name__ == "__main__":
    main()
