import json

from app.integrations.dux.client import DuxClient

c = DuxClient()

respuesta = c.get(
    "v2/items",
    params={
        "id_empresa": c.id_empresa,
        "limit": 1,
        "offset": 0,
    },
)

producto = respuesta["datos"][0]

print(json.dumps(
    producto,
    indent=2,
    ensure_ascii=False,
))

with open(
    "producto_ejemplo.json",
    "w",
    encoding="utf-8",
) as archivo:
    json.dump(
        producto,
        archivo,
        indent=2,
        ensure_ascii=False,
    )

print("\n✅ Archivo generado")