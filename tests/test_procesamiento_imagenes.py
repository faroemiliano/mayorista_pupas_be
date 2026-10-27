from io import BytesIO

import pytest
from PIL import Image

from app.services.procesamiento_imagenes_service import ImagenInvalidaError, procesar_imagen_catalogo


def _imagen(formato: str, *, size=(2400, 1200), alpha=False) -> bytes:
    salida = BytesIO()
    Image.new("RGBA" if alpha else "RGB", size, (30, 40, 50, 120) if alpha else (30, 40, 50)).save(salida, format=formato)
    return salida.getvalue()


def test_normaliza_jpeg_grande_a_webp_y_lo_redimensiona():
    resultado = procesar_imagen_catalogo(_imagen("JPEG"), media_type_declarado="image/jpeg")
    assert resultado.media_type == "image/webp"
    assert resultado.ancho_original == 2400
    assert resultado.ancho == 2000
    assert resultado.alto == 1000
    assert resultado.contenido.startswith(b"RIFF")


def test_conserva_transparencia_de_png():
    resultado = procesar_imagen_catalogo(_imagen("PNG", alpha=True), media_type_declarado="image/png")
    with Image.open(BytesIO(resultado.contenido)) as imagen:
        assert imagen.mode == "RGBA"


def test_rechaza_archivo_con_extension_imagen_pero_contenido_invalido():
    with pytest.raises(ImagenInvalidaError):
        procesar_imagen_catalogo(b"no soy una imagen", media_type_declarado="image/jpeg")
