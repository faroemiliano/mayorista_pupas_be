"""Lectura acotada de Google Analytics 4 para el panel administrativo.

Las credenciales viven sólo en variables de entorno del backend. El resultado
se mantiene en memoria por algunos minutos para no hacer una llamada a Google
cada vez que un administrador abre o cambia de sección.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
import json
from threading import Lock
from time import monotonic
from typing import Any

from google.auth.transport.requests import AuthorizedSession
from google.oauth2 import service_account

from app.core.config import settings


_GOOGLE_SCOPE = "https://www.googleapis.com/auth/analytics.readonly"
_GA4_BASE_URL = "https://analyticsdata.googleapis.com/v1beta"
_CACHE_SECONDS = 600
_REALTIME_CACHE_SECONDS = 60
_cache: dict[str, tuple[float, dict[str, Any]]] = {}
_realtime_cache: tuple[float, int | None] | None = None
_cache_lock = Lock()


class GA4AnalyticsError(Exception):
    """Error seguro para mostrar al administrador sin filtrar credenciales."""


def _valor_metrica(row: dict[str, Any], indice: int) -> int:
    values = row.get("metricValues", [])
    if indice >= len(values):
        return 0
    try:
        return int(float(values[indice].get("value", 0)))
    except (TypeError, ValueError):
        return 0


def _valor_dimension(row: dict[str, Any], indice: int) -> str:
    values = row.get("dimensionValues", [])
    if indice >= len(values):
        return ""
    return str(values[indice].get("value", ""))


def _sesion_ga4() -> AuthorizedSession:
    if not settings.ga4_analytics_configurado:
        raise GA4AnalyticsError("Google Analytics todavía no está configurado en el servidor.")
    try:
        account_info = json.loads(settings.GA4_SERVICE_ACCOUNT_JSON)
        credentials = service_account.Credentials.from_service_account_info(
            account_info,
            scopes=[_GOOGLE_SCOPE],
        )
    except (json.JSONDecodeError, ValueError, TypeError) as error:
        raise GA4AnalyticsError("La credencial de Google Analytics no tiene un formato válido.") from error
    return AuthorizedSession(credentials)


def _post_report(session: AuthorizedSession, endpoint: str, body: dict[str, Any]) -> dict[str, Any]:
    url = f"{_GA4_BASE_URL}/properties/{settings.GA4_PROPERTY_ID.strip()}:{endpoint}"
    try:
        response = session.post(url, json=body, timeout=20)
    except Exception as error:  # Errores de red de Google Auth/requests.
        raise GA4AnalyticsError("No se pudo contactar a Google Analytics. Probá nuevamente en unos minutos.") from error
    if not response.ok:
        raise GA4AnalyticsError("Google Analytics rechazó la consulta. Verificá el acceso de la cuenta de servicio a la propiedad.")
    return response.json()


def _consulta_normal(session: AuthorizedSession, days: int, dimensions: list[str], metrics: list[str], *, fecha: date | None = None, limit: int = 100, order_metric: str | None = None) -> dict[str, Any]:
    date_range = (
        {"startDate": fecha.isoformat(), "endDate": fecha.isoformat()}
        if fecha
        # GA incluye ambos extremos. Para mostrar exactamente 7 o 30 días
        # contando hoy, el inicio debe retroceder un día menos.
        else {"startDate": f"{days - 1}daysAgo", "endDate": "today"}
    )
    body: dict[str, Any] = {
        "dateRanges": [date_range],
        "dimensions": [{"name": dimension} for dimension in dimensions],
        "metrics": [{"name": metric} for metric in metrics],
        "limit": str(limit),
    }
    if order_metric:
        body["orderBys"] = [{"metric": {"metricName": order_metric}, "desc": True}]
    return _post_report(session, "runReport", body)


def _obtener_activos_ahora(session: AuthorizedSession) -> int | None:
    global _realtime_cache
    with _cache_lock:
        if _realtime_cache and monotonic() - _realtime_cache[0] < _REALTIME_CACHE_SECONDS:
            return _realtime_cache[1]
    try:
        report = _post_report(session, "runRealtimeReport", {"metrics": [{"name": "activeUsers"}]})
        rows = report.get("rows", [])
        value = _valor_metrica(rows[0], 0) if rows else 0
    except GA4AnalyticsError:
        # El informe histórico sigue siendo útil aunque la parte en tiempo real
        # no esté disponible momentáneamente.
        value = None
    with _cache_lock:
        _realtime_cache = (monotonic(), value)
    return value


def _formatear_fecha(value: str) -> tuple[str, str]:
    try:
        parsed = datetime.strptime(value, "%Y%m%d")
        return parsed.date().isoformat(), parsed.strftime("%d/%m")
    except ValueError:
        return value, value


def obtener_trafico_ga4(days: int = 7, fecha: date | str | None = None) -> dict[str, Any]:
    if days not in {7, 30}:
        raise ValueError("El período permitido es de 7 o 30 días.")
    # La ruta entrega un ``date``; aceptar texto también mantiene la función
    # segura para llamadas internas y evita que una fecha de query sin tipar
    # rompa el panel.
    if isinstance(fecha, str):
        try:
            fecha = date.fromisoformat(fecha)
        except ValueError as error:
            raise ValueError("La fecha debe tener formato AAAA-MM-DD.") from error
    fecha_consultada = fecha
    cache_key = f"fecha:{fecha_consultada.isoformat()}" if fecha_consultada else f"dias:{days}"
    with _cache_lock:
        cached = _cache.get(cache_key)
        if cached and monotonic() - cached[0] < _CACHE_SECONDS:
            return cached[1]

    session = _sesion_ga4()
    resumen_report = _consulta_normal(session, days, [], ["activeUsers", "sessions", "screenPageViews"], fecha=fecha_consultada, limit=1)
    diario_report = _consulta_normal(session, days, ["date"], ["activeUsers", "sessions", "screenPageViews"], fecha=fecha_consultada, limit=days + 2)
    paginas_report = _consulta_normal(session, days, ["pagePath"], ["screenPageViews", "activeUsers"], fecha=fecha_consultada, limit=10, order_metric="screenPageViews")
    dispositivos_report = _consulta_normal(session, days, ["deviceCategory"], ["activeUsers"], fecha=fecha_consultada, limit=10, order_metric="activeUsers")

    resumen_rows = resumen_report.get("rows", [])
    resumen_row = resumen_rows[0] if resumen_rows else {}
    serie_diaria = []
    for row in diario_report.get("rows", []):
        fecha_item, etiqueta = _formatear_fecha(_valor_dimension(row, 0))
        serie_diaria.append({
            "fecha": fecha_item,
            "etiqueta": etiqueta,
            "usuarios": _valor_metrica(row, 0),
            "sesiones": _valor_metrica(row, 1),
            "vistas_paginas": _valor_metrica(row, 2),
        })
    serie_diaria.sort(key=lambda item: item["fecha"])

    result = {
        "dias": days,
        "fecha": fecha_consultada.isoformat() if fecha_consultada else None,
        "resumen": {
            "usuarios": _valor_metrica(resumen_row, 0),
            "sesiones": _valor_metrica(resumen_row, 1),
            "vistas_paginas": _valor_metrica(resumen_row, 2),
            "usuarios_activos_ahora": _obtener_activos_ahora(session),
        },
        "serie_diaria": serie_diaria,
        "paginas_populares": [
            {
                "ruta": _valor_dimension(row, 0) or "/",
                "vistas_paginas": _valor_metrica(row, 0),
                "usuarios": _valor_metrica(row, 1),
            }
            for row in paginas_report.get("rows", [])
        ],
        "dispositivos": [
            {"dispositivo": _valor_dimension(row, 0), "usuarios": _valor_metrica(row, 0)}
            for row in dispositivos_report.get("rows", [])
        ],
        "actualizado_en": datetime.now(timezone.utc).isoformat(),
        "fuente": "Google Analytics 4",
    }
    with _cache_lock:
        _cache[cache_key] = (monotonic(), result)
    return result
