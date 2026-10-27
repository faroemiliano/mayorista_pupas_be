"""Ejecutable de solo lectura para auditar las imágenes del catálogo en R2.

Uso en la Shell de Render:
    python -m app.scripts.diagnosticar_imagenes_r2
"""

from __future__ import annotations

import json

from app.database.session import SessionLocal
from app.services.diagnostico_imagenes_r2_service import obtener_diagnostico_avanzado_imagenes_r2


def main() -> None:
    with SessionLocal() as db:
        resultado = obtener_diagnostico_avanzado_imagenes_r2(db)
    print(json.dumps(resultado, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
