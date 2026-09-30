from html import escape


def construir_email_restablecimiento(
    *,
    nombre: str | None,
    enlace: str,
    logo_url: str,
) -> tuple[str, str]:
    """Devuelve las versiones de texto y HTML del email de restablecimiento."""
    nombre_cliente = (nombre or "").strip()
    saludo_texto = f"Hola, {nombre_cliente}." if nombre_cliente else "Hola."
    saludo_html = escape(saludo_texto)
    enlace_html = escape(enlace, quote=True)
    logo_html = escape(logo_url, quote=True)

    texto = (
        f"{saludo_texto}\n\n"
        "Recibimos una solicitud para crear una nueva contraseña para tu cuenta "
        "de Pupas Mayorista.\n\n"
        f"Crear mi nueva contraseña: {enlace}\n\n"
        "El enlace vence en una hora y se puede usar una sola vez. "
        "Si no solicitaste este cambio, podés ignorar este email."
    )
    html = f"""<!doctype html>
<html lang="es">
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Creá tu nueva contraseña de Pupas</title>
  </head>
  <body style="margin:0;background:#f5f1ed;color:#24201d;font-family:Arial,sans-serif;">
    <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="background:#f5f1ed;padding:32px 16px;">
      <tr>
        <td align="center">
          <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="max-width:560px;background:#ffffff;border:1px solid #e8dfd7;">
            <tr>
              <td align="center" style="padding:32px 32px 22px;border-bottom:1px solid #eee7e1;">
                <img src="{logo_html}" width="180" alt="Pupas" style="display:block;width:180px;max-width:70%;height:auto;border:0;">
                <div style="margin-top:12px;font-size:11px;font-weight:700;letter-spacing:2px;text-transform:uppercase;color:#756351;">Tienda mayorista</div>
              </td>
            </tr>
            <tr>
              <td style="padding:36px 40px 40px;">
                <p style="margin:0 0 18px;font-size:16px;line-height:1.6;">{saludo_html}</p>
                <h1 style="margin:0 0 18px;font-family:Georgia,serif;font-size:32px;line-height:1.15;font-weight:600;color:#1d1a18;">Creá tu nueva contraseña</h1>
                <p style="margin:0 0 26px;font-size:15px;line-height:1.7;color:#5f5751;">Recibimos una solicitud para crear una nueva contraseña para tu cuenta de Pupas Mayorista.</p>
                <table role="presentation" cellspacing="0" cellpadding="0">
                  <tr>
                    <td bgcolor="#171513" style="border-radius:2px;">
                      <a href="{enlace_html}" style="display:inline-block;padding:15px 24px;color:#ffffff;text-decoration:none;font-size:14px;font-weight:700;">Crear mi nueva contraseña</a>
                    </td>
                  </tr>
                </table>
                <p style="margin:26px 0 0;font-size:13px;line-height:1.6;color:#756d67;">El enlace vence en una hora y se puede usar una sola vez.</p>
                <p style="margin:12px 0 0;font-size:13px;line-height:1.6;color:#756d67;">Si no solicitaste este cambio, podés ignorar este email: tu cuenta seguirá protegida.</p>
              </td>
            </tr>
            <tr>
              <td align="center" style="padding:20px 32px;background:#171513;color:#d8cec6;font-size:11px;line-height:1.6;">
                Pupas Mayorista · Este es un mensaje automático
              </td>
            </tr>
          </table>
        </td>
      </tr>
    </table>
  </body>
</html>"""
    return texto, html
