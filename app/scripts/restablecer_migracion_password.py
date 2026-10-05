"""Vuelve a dejar pendiente el cambio de clave de una cuenta migrada.

Se ejecuta únicamente desde una consola controlada (por ejemplo, Render Shell):
    python -m app.scripts.restablecer_migracion_password correo@ejemplo.com
"""

import sys

from app.database.session import SessionLocal
from app.repositories.usuario_repository import get_usuario_by_email


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit(
            "Uso: python -m app.scripts.restablecer_migracion_password correo@ejemplo.com"
        )

    email = sys.argv[1].strip().lower()
    with SessionLocal() as db:
        usuario = get_usuario_by_email(db, email)
        if usuario is None:
            raise SystemExit("No existe una cuenta con ese email.")
        if usuario.rol == "admin":
            raise SystemExit("No se puede restablecer una cuenta administradora.")

        usuario.password_hash = None
        usuario.requiere_migracion_password = True
        usuario.reset_password_token_hash = None
        usuario.reset_password_expira_en = None
        db.commit()

        print(f"Cuenta {usuario.email} marcada como pendiente de cambio de clave.")


if __name__ == "__main__":
    main()
