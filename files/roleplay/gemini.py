"""
Unico punto de contacto con Gemini.

Los servicios llaman a `generar_json(prompt, Esquema, que_hacer)`: pide la
salida estructurada con `response_schema` (nada de parsear JSON
"prometido" en texto libre), la valida con pydantic, y si falla deja un
mensaje que termina diciendo que boton apretar.

Claves: GEMINI_API_KEY o GEMINI_API_KEYS (varias separadas por comas,
puntos y comas o espacios) en el .env de la raiz del proyecto.

La libreria `google.genai` se importa recien en la primera llamada: tarda
~1,4 s en cargar y no hace falta para abrir la ventana.
"""

import os
import re
from functools import lru_cache
from typing import Any, Optional, TypeVar

from dotenv import load_dotenv
from pydantic import BaseModel, ValidationError

from roleplay import config

load_dotenv(config.ARCHIVO_ENV)

MODELS = ["gemini-2.5-flash", "gemini-3.5-flash"]

# Reintentos del propio SDK solo para errores del servidor (5xx). El 429
# (cuota) NO se reintenta aca: casi siempre es la cuota diaria del tier
# gratis y reintentarlo solo hace esperar ~1 minuto por modelo; el
# fallback de abajo salta directo al siguiente modelo.
REINTENTOS_SERVIDOR = {
    "attempts": 3,
    "initial_delay": 2.0,
    "max_delay": 8.0,
    "http_status_codes": [500, 502, 503, 504],
}

Esquema = TypeVar("Esquema", bound=BaseModel)


class FaltaApiKey(RuntimeError):
    """No hay ninguna key configurada (reintentar no sirve de nada)."""


def get_gemini_api_keys(api_key: Optional[str] = None) -> list[str]:
    """Claves a usar, en orden: `api_key` explicita, GEMINI_API_KEYS
    (lista) o GEMINI_API_KEY (una sola)."""
    if api_key:
        return [api_key]

    lista = os.environ.get("GEMINI_API_KEYS")
    if lista:
        return [clave.strip() for clave in re.split(r"[;,\s]+", lista) if clave.strip()]

    unica = os.environ.get("GEMINI_API_KEY")
    return [unica] if unica else []


@lru_cache(maxsize=None)
def _cliente(api_key: str):
    """Un cliente por key, reusado entre llamadas (reaprovecha la conexion)."""
    from google import genai
    from google.genai import types

    return genai.Client(
        api_key=api_key,
        http_options=types.HttpOptions(retry_options=types.HttpRetryOptions(**REINTENTOS_SERVIDOR)),
    )


def is_rate_limited_error(exc: Exception) -> bool:
    """429: se acabo la cuota de ESTE modelo con esta key. Las cuotas son
    por modelo, asi que conviene probar otro modelo con la MISMA key."""
    from google.genai import errors

    return isinstance(exc, errors.ClientError) and getattr(exc, "code", None) == 429


def is_key_auth_error(exc: Exception) -> bool:
    """401/403: la key esta mal, revocada o sin permiso. Aplica a la key
    entera, asi que se salta directo a la siguiente key."""
    from google.genai import errors

    return isinstance(exc, errors.ClientError) and getattr(exc, "code", None) in {401, 403}


def generate_content_with_fallback(
    contents: Any,
    config: Any,
    api_key: Optional[str] = None,
    models: Optional[list[str]] = None,
) -> Any:
    """Prueba cada modelo con cada key: todos los modelos de una key antes
    de pasar a la siguiente.

    - 5xx: siguiente modelo (misma key).
    - 429: siguiente modelo (misma key).
    - 401/403: siguiente key.
    - otro error (ej. 400): falla de inmediato, reintentar no lo arregla.
    """
    from google.genai import errors

    keys = get_gemini_api_keys(api_key)
    if not keys:
        raise FaltaApiKey(
            "Falta GEMINI_API_KEY (o GEMINI_API_KEYS) en el archivo .env de la "
            "carpeta del proyecto. Conseguis una gratis en https://aistudio.google.com/apikey"
        )

    models = models or MODELS
    ultimo_error = None

    for key in keys:
        cliente = _cliente(key)
        for model in models:
            try:
                return cliente.models.generate_content(model=model, contents=contents, config=config)
            except errors.ServerError as exc:
                ultimo_error = exc  # modelo saturado: probamos el siguiente
            except errors.ClientError as exc:
                if is_rate_limited_error(exc):
                    ultimo_error = exc  # sin cuota en este modelo: el siguiente
                elif is_key_auth_error(exc):
                    ultimo_error = exc
                    break  # esta key no sirve: la siguiente key
                else:
                    raise

    raise RuntimeError(
        "Gemini esta rechazando los pedidos (mucha demanda, limite de uso o "
        "problema con las keys) y ya se probaron todas las combinaciones de "
        f"key/modelo ({', '.join(models)})."
    ) from ultimo_error


def generar_json(
    prompt: str,
    esquema: type[Esquema],
    que_hacer: str,
    adjunto: Optional[tuple[bytes, str]] = None,
    api_key: Optional[str] = None,
) -> Esquema:
    """Pide a Gemini una respuesta con la forma de `esquema` y la devuelve
    validada.

    `que_hacer` es lo que se le dice al usuario si falla, ej. "Esperate un
    poco y apreta 'Regenerar entrevista' de nuevo."
    `adjunto` es (bytes, tipo MIME), ej. una captura (image/png) o una
    respuesta grabada (audio/wav).
    """
    from google.genai import types

    contenido: Any = prompt
    if adjunto is not None:
        datos, tipo_mime = adjunto
        contenido = [prompt, types.Part.from_bytes(data=datos, mime_type=tipo_mime)]

    configuracion = types.GenerateContentConfig(
        response_mime_type="application/json",
        response_schema=esquema,
    )

    try:
        respuesta = generate_content_with_fallback(contenido, configuracion, api_key=api_key)
    except FaltaApiKey:
        raise
    except RuntimeError as exc:
        raise RuntimeError(f"{exc} {que_hacer}") from exc

    texto = respuesta.text or ""
    try:
        return esquema.model_validate_json(texto)
    except ValidationError as exc:
        raise RuntimeError(
            f"Gemini respondio algo que no tiene el formato esperado. {que_hacer}\n\n{texto[:500]}"
        ) from exc
