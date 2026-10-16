"""
IA hibrida (opcional): reescribe con la IA lo que el motor local ya decidio,
para que la prensa y los hinchas contesten a lo que de verdad escribio el
jugador. Cascada:

1. Groq (llama-3.3-70b-versatile; con 429/5xx, llama-3.1-8b-instant);
2. Gemini por REST (gemini-2.5-flash; si no, gemini-2.5-flash-lite);
3. None: el que llama usa lo del motor local (narrador + lexico + cruce),
   que se calcula SIEMPRE antes. Nunca lanza excepciones.

Solo libreria estandar (urllib): no suma nada al arranque. Las claves
(GROQ_API_KEY(S) / GEMINI_API_KEY(S)) salen de ajustes.json y despues del
.env de la carpeta de datos; varias claves van separadas por coma. Con
`sin_ia` en los ajustes, o EAFC_SIN_IA=1 (las pruebas), no sale nada a la red.

Los numeros reales (resultados, goles, tablas) y los nombres los sigue
poniendo el codigo: la IA solo recibe esos hechos y tiene prohibido
inventar otros. Nunca loguear ni mostrar las claves.
"""

import json
import os
import time
import urllib.error
import urllib.request
from typing import Optional

from roleplay import ajustes, config

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODELOS = ("llama-3.3-70b-versatile", "llama-3.1-8b-instant")
GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/{modelo}:generateContent"
GEMINI_MODELOS = ("gemini-2.5-flash", "gemini-2.5-flash-lite")
TEMPERATURA = 0.75
TIMEOUT = 6.0
TOPE_TOTAL = 2  # toda la cascada tarda a lo sumo TOPE_TOTAL x timeout

REGLAS = (
    "Escribis en espanol (registro chileno/rioplatense informal, natural). "
    "Usa SOLO los datos que te dan: nunca inventes resultados, goles, estadisticas, posiciones en la tabla, "
    "fichajes ni nombres de personas reales que no esten en los datos. Si falta un dato, no lo menciones. "
    "Sin markdown ni emojis salvo que se pidan. Responde SOLO con un objeto JSON valido."
)

ultimo = {"proveedor": "", "modelo": "", "ms": 0}  # para "Probar IA" y el diagnostico


class _Fallo(Exception):
    """Algo salio mal con un modelo; `otra_clave` si la clave no sirve."""

    def __init__(self, motivo: str, otra_clave: bool = False):
        super().__init__(motivo)
        self.otra_clave = otra_clave


# ---- configuracion ----


def desactivada() -> bool:
    return os.environ.get("EAFC_SIN_IA") == "1" or bool(ajustes.leer().get("sin_ia"))


def _del_env() -> dict:
    archivo = config.CARPETA_DATOS / ".env"
    valores = {}
    try:
        for linea in archivo.read_text(encoding="utf-8").splitlines():
            if "=" in linea and not linea.lstrip().startswith("#"):
                clave, valor = linea.split("=", 1)
                valores[clave.strip()] = valor.strip().strip('"').strip("'")
    except OSError:
        pass
    return valores


def _separar(valor) -> list[str]:
    if isinstance(valor, (list, tuple)):
        return [str(v).strip() for v in valor if str(v).strip()]
    return [v.strip() for v in str(valor or "").split(",") if v.strip()]


def claves(proveedor: str) -> list[str]:
    """Las claves de "groq" o "gemini": primero ajustes.json, despues el .env."""
    nombre = proveedor.upper()
    guardados = ajustes.leer()
    for origen in (guardados, _del_env()):
        for clave in (f"{nombre}_API_KEYS", f"{nombre}_API_KEY", f"{proveedor}_api_keys", f"{proveedor}_api_key"):
            encontradas = _separar(origen.get(clave))
            if encontradas:
                return list(dict.fromkeys(encontradas))
    return []


def estado() -> str:
    """Para el diagnostico (sin mostrar las claves)."""
    if desactivada():
        return "desactivada (solo motor local)"
    partes = [f"{p.capitalize()}: {len(claves(p))} clave(s)" if claves(p) else f"{p.capitalize()}: sin clave"
              for p in ("groq", "gemini")]
    if not any(claves(p) for p in ("groq", "gemini")):
        partes.append("sin claves: usa el motor local")
    return " · ".join(partes)


# ---- los proveedores ----


def _post(url: str, cuerpo: dict, cabeceras: dict, timeout: float) -> dict:
    pedido = urllib.request.Request(
        url, data=json.dumps(cuerpo).encode("utf-8"), method="POST",
        headers={"Content-Type": "application/json", "User-Agent": "EAFC26-Roleplay", **cabeceras},
    )
    try:
        with urllib.request.urlopen(pedido, timeout=timeout) as respuesta:
            return json.loads(respuesta.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raise _Fallo(f"HTTP {exc.code}", otra_clave=exc.code in (400, 401, 403)) from None
    except (urllib.error.URLError, TimeoutError, OSError, ValueError) as exc:
        raise _Fallo(type(exc).__name__) from None


def _json_de(texto: str) -> dict:
    texto = (texto or "").strip()
    if texto.startswith("```"):  # por si viene envuelto en un bloque de codigo
        texto = texto.strip("`").removeprefix("json").strip()
    try:
        datos = json.loads(texto)
    except ValueError:
        raise _Fallo("no devolvio JSON") from None
    if not isinstance(datos, dict):
        raise _Fallo("no devolvio un objeto")
    return datos


def _groq(clave: str, modelo: str, sistema: str, usuario: str, timeout: float) -> dict:
    respuesta = _post(GROQ_URL, {
        "model": modelo, "temperature": TEMPERATURA, "response_format": {"type": "json_object"},
        "messages": [{"role": "system", "content": sistema}, {"role": "user", "content": usuario}],
    }, {"Authorization": f"Bearer {clave}"}, timeout)
    try:
        return _json_de(respuesta["choices"][0]["message"]["content"])
    except (KeyError, IndexError, TypeError):
        raise _Fallo("respuesta rara") from None


def _gemini(clave: str, modelo: str, sistema: str, usuario: str, timeout: float) -> dict:
    respuesta = _post(GEMINI_URL.format(modelo=modelo), {
        "systemInstruction": {"parts": [{"text": sistema}]},
        "contents": [{"role": "user", "parts": [{"text": usuario}]}],
        "generationConfig": {"temperature": TEMPERATURA, "responseMimeType": "application/json"},
    }, {"x-goog-api-key": clave}, timeout)
    try:
        return _json_de(respuesta["candidates"][0]["content"]["parts"][0]["text"])
    except (KeyError, IndexError, TypeError):
        raise _Fallo("respuesta rara") from None


PROVEEDORES = (("groq", GROQ_MODELOS, _groq), ("gemini", GEMINI_MODELOS, _gemini))


def pedir_json(prompt_sistema: str, prompt_usuario: str, esquema_ejemplo: dict,
               timeout: float = TIMEOUT) -> Optional[dict]:
    """El JSON que devolvio el primer proveedor que contesto, o None (sin
    claves, sin internet, sin cuota, desactivada). Nunca lanza."""
    try:
        if desactivada():
            return None
        sistema = (f"{prompt_sistema}\n\n{REGLAS}\nForma exacta del JSON (mismas claves y tipos): "
                   f"{json.dumps(esquema_ejemplo, ensure_ascii=False)}")
        limite = time.monotonic() + timeout * TOPE_TOTAL
        for proveedor, modelos, llamar in PROVEEDORES:
            for clave in claves(proveedor):
                for modelo in modelos:
                    queda = limite - time.monotonic()
                    if queda <= 0.3:
                        return None
                    inicio = time.monotonic()
                    try:
                        datos = llamar(clave, modelo, sistema, prompt_usuario, min(timeout, queda))
                    except _Fallo as fallo:
                        if fallo.otra_clave:
                            break  # esta clave no sirve: la siguiente
                        continue  # cuota, caida o respuesta rara: el siguiente modelo
                    ultimo.update(proveedor=proveedor, modelo=modelo, ms=round((time.monotonic() - inicio) * 1000))
                    return datos
        return None
    except Exception:  # noqa: BLE001  (pase lo que pase, queda el motor local)
        return None


def probar() -> str:
    """Para el boton "Probar IA" de Ajustes (corre en un hilo)."""
    if desactivada():
        return "La IA esta desactivada: se usa solo el motor local."
    if not claves("groq") and not claves("gemini"):
        return "No hay ninguna clave: se usa el motor local."
    inicio = time.monotonic()
    datos = pedir_json("Sos una prueba de conexion.", 'Contesta {"ok": true}.', {"ok": True})
    if datos is None:
        return (f"Ningun proveedor contesto ({round((time.monotonic() - inicio) * 1000)} ms). "
                "Revisa las claves o la conexion; mientras, se usa el motor local.")
    return f"Respondio {ultimo['proveedor'].capitalize()} ({ultimo['modelo']}) en {ultimo['ms']} ms."


# ---- piezas para armar los pedidos ----


def texto(valor, maximo: int = 600) -> str:
    """Un texto de la IA, limpio y acotado ("" si no sirve)."""
    if not isinstance(valor, str):
        return ""
    limpio = " ".join(valor.replace("{", "").replace("}", "").split())
    return limpio[:maximo].rstrip()


def entero(valor, tope: int, defecto: int) -> int:
    try:
        return max(-tope, min(tope, round(float(valor))))
    except (TypeError, ValueError):
        return defecto


def ficha(perfil) -> str:
    return (f"Jugador: {perfil.nombre_jugador} · club: {perfil.club_actual or 'sin club'} · "
            f"posicion: {getattr(perfil, 'posicion', '') or '?'} · personalidad: {perfil.personalidad or '?'}")


def describir_cruces(cruces, cuantos: int = 4) -> str:
    """Lo que pasa en su vida (servicios/cruce.py), del mas jugoso al menos."""
    lineas = [f"- {c.tipo}: {json.dumps(c.datos, ensure_ascii=False, default=str)}" for c in list(cruces)[:cuantos]]
    return "\n".join(lineas) or "- (nada especial)"


def comentarios_validos(lista, minimo: int = 2, maximo: int = 5) -> list[dict]:
    """[{autor, texto, tono}] de la IA, limpios; [] si no alcanzan."""
    if not isinstance(lista, list):
        return []
    validos = []
    for c in lista:
        if not isinstance(c, dict):
            continue
        autor, dicho = texto(c.get("autor"), 40).replace(" ", "_"), texto(c.get("texto"), 280)
        if not autor or not dicho:
            continue
        tono = c.get("tono") if c.get("tono") in ("positivo", "negativo", "neutral", "gracioso") else "neutral"
        validos.append({"autor": autor if autor.startswith("@") else "@" + autor, "texto": dicho, "tono": tono})
    return validos[:maximo] if len(validos) >= minimo else []


def cita_literal(cita, textos: list[str]) -> str:
    """La cita de la IA solo vale si son palabras textuales del jugador."""
    limpia = texto(cita, 200).strip("«»\"' ")
    def normal(s: str) -> str:
        return " ".join(s.lower().split())
    return limpia if limpia and normal(limpia) in normal(" ".join(textos)) else ""
