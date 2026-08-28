import getpass
import sys

from app.core.security import hashear_password
from app.database.session import SessionLocal
from app.repositories.usuario_repository import get_usuario_by_email


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit(
            "Uso: python -m app.scripts.establecer_password correo@gmail.com"
        )

    email = sys.argv[1].strip().lower()
    password = getpass.getpass("Nueva contraseña: ")
    confirmation = getpass.getpass("Confirmar contraseña: ")

    if len(password) < 8:
        raise SystemExit("La contraseña debe tener al menos 8 caracteres.")
    if password != confirmation:
        raise SystemExit("Las contraseñas no coinciden.")

    with SessionLocal() as db:
        usuario = get_usuario_by_email(db, email)
        if usuario is None:
            raise SystemExit("No existe una cuenta con ese email.")

        usuario.password_hash = hashear_password(password)
        usuario.activo = True
        db.commit()

        print(
            "Contraseña actualizada correctamente. "
            f"Rol conservado: {usuario.rol}."
        )


if __name__ == "__main__":
    main()
