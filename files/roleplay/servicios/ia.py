"""
IA hibrida (opcional): reescribe con la IA lo que el motor local ya decidio,
para que la prensa y los hinchas contesten a lo que de verdad escribio el
jugador. Cascada:

1. Groq (openai/gpt-oss-120b; con 429/5xx, gpt-oss-20b y qwen; si Groq dio de
   baja TODOS esos modelos (404), pregunta cuales tiene y prueba esos);
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

Roleplay vivo (2026-10-20, Simon: "que se sienta vivo, no como un guion"):
con `jugador=` el pedido lleva la memoria del roleplay (servicios/memoria.py:
lo que dijo, lo que le paso, las tramas abiertas) y la consigna VOZ. La
guardia de hechos (`_sin_numeros_inventados`) vacia todo texto de la
respuesta con un numero que no este en el pedido: ese campo cae al motor local.
"""

import json
import os
import re
import time
import urllib.error
import urllib.request
from typing import Optional

from roleplay import ajustes, config

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODELOS_URL = "https://api.groq.com/openai/v1/models"
# los Llama 3.x se dieron de baja en 2026 (404 model_not_found): por eso el descubrimiento
GROQ_MODELOS = ("openai/gpt-oss-120b", "openai/gpt-oss-20b", "qwen/qwen3.8-27b")
GROQ_FAMILIAS = ("gpt-oss", "llama", "qwen", "gemma", "mistral", "kimi", "deepseek")  # modelos de chat
GROQ_NO_CHAT = ("guard", "whisper", "orpheus", "tts")
GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/{modelo}:generateContent"
GEMINI_MODELOS = ("gemini-2.5-flash", "gemini-2.5-flash-lite")
TEMPERATURA = 0.75
TIMEOUT = 6.0
TOPE_TOTAL = 2  # toda la cascada tarda a lo sumo TOPE_TOTAL x timeout

REGLAS = (
    "REGLAS DE ORO (si una se rompe, el texto se descarta):\n"
    "1. Espanol natural, registro chileno/rioplatense informal. Sin markdown. Emojis solo si la tarea los pide.\n"
    "2. SOLO lo que dicen los datos. Lo que no esta, NO EXISTE: nada de estadios ni ciudades, entrenamientos, "
    "lesiones, clima, publico, minutos o forma de los goles (cabeza, tiro libre), asistencias, tecnicos, "
    "companeros, fichajes ni premios que no aparezcan. Ningun nombre propio que no este en los datos.\n"
    "3. Los numeros, tal cual los datos: ninguno de mas. Un marcador \"A 1-3 B\" es del partido: gano B, de "
    "visitante. Los goles del jugador son solo los que dicen los datos como SUYOS.\n"
    "4. Cada dato es de quien es: lo del rival (su goleador, su racha, su tabla) es del rival, nunca del jugador.\n"
    "5. Nada de causas, culpas ni cargos que los datos no digan (capitan, lider): una victoria o un buen numero "
    "nunca son motivo de critica; las criticas salen de lo que el jugador DIJO o de un mal numero SUYO.\n"
    "6. No cambies de que se trata un hecho: si es \"25 goles en la temporada\", son goles en partidos, no en "
    "un entrenamiento; si es una cena, no es una fiesta.\n"
    "7. Responde SOLO con un objeto JSON valido, con la forma pedida."
)

VOZ = (
    "Esto es un roleplay VIVO, no un guion: escribi como gente real de ese mundo (periodistas con opinion "
    "propia, hinchas con memoria, personas con su manera de hablar). Usa la memoria del roleplay para dar "
    "continuidad cuando venga al caso (retomar algo que dijo, una trama abierta, como viene), sin repetir "
    "titulares ni frases que ya estan ahi. Varia la forma: nada de plantillas ni frases hechas de diario "
    "(\"genera dudas\", \"alimenta la polemica\", \"no paso desapercibido\", \"zona mixta\"). La memoria es "
    "contexto: no saques de ahi datos nuevos ni la cuentes entera. Las tramas y lo que dijo son de ANTES: no los "
    "des como hechos de hoy (un rival del que hablo antes no es el proximo). Toda opinion tiene que ser coherente "
    "con la memoria: no le reproches un rendimiento que es bueno ni elogies uno malo."
)

ultimo = {"proveedor": "", "modelo": "", "ms": 0}  # para "Probar IA" y el diagnostico


class _Fallo(Exception):
    """Algo salio mal con un modelo; `otra_clave` si la clave no sirve."""

    def __init__(self, motivo: str, otra_clave: bool = False, no_existe: bool = False):
        super().__init__(motivo)
        self.otra_clave = otra_clave
        self.no_existe = no_existe  # el modelo ya no esta (404)


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
        raise _Fallo(f"HTTP {exc.code}", otra_clave=exc.code in (401, 403), no_existe=exc.code == 404) from None
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
    cuerpo = {
        "model": modelo, "temperature": TEMPERATURA, "response_format": {"type": "json_object"},
        "messages": [{"role": "system", "content": sistema}, {"role": "user", "content": usuario}],
    }
    if "gpt-oss" in modelo:
        cuerpo["reasoning_effort"] = "low"  # razona poco: ~0,5 s
    respuesta = _post(GROQ_URL, cuerpo, {"Authorization": f"Bearer {clave}"}, timeout)
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


def modelos_de_groq(clave: str, timeout: float) -> list[str]:
    """Los modelos de chat que Groq tiene hoy (para cuando dio de baja los nuestros)."""
    pedido = urllib.request.Request(GROQ_MODELOS_URL, headers={"User-Agent": "EAFC26-Roleplay",
                                                                "Authorization": f"Bearer {clave}"})
    try:
        with urllib.request.urlopen(pedido, timeout=timeout) as respuesta:
            datos = json.loads(respuesta.read().decode("utf-8"))
        ids = [m["id"] for m in datos["data"] if m.get("active", True)]
    except Exception:  # noqa: BLE001
        return []
    return [i for i in ids if any(f in i for f in GROQ_FAMILIAS) and not any(n in i for n in GROQ_NO_CHAT)]


PROVEEDORES = (("groq", GROQ_MODELOS, _groq), ("gemini", GEMINI_MODELOS, _gemini))


_NUMERO = re.compile(r"\d+(?:[.,]\d+)*")


def _numeros_de(texto: str) -> set:
    """Los numeros de un texto, enteros y por partes ("1.888.150" -> 1.888.150, 1888150, 1, 888, 150)."""
    vistos = set()
    for numero in _NUMERO.findall(texto):
        vistos.add(numero)
        vistos.add(re.sub(r"[.,]", "", numero))
        vistos.update(re.split(r"[.,]", numero))
    return vistos


def _sin_numeros_inventados(valor, permitidos: set, fuente: str = ""):
    """La respuesta con "" en cada texto que trae un numero que no se le paso o
    un nombre propio que no esta en el pedido (`fuente`, ya normalizada)."""
    if isinstance(valor, str):
        numeros_ok = all(n in permitidos or re.sub(r"[.,]", "", n) in permitidos for n in _NUMERO.findall(valor))
        return valor if numeros_ok and not (fuente and nombres_inventados(valor, fuente)) else ""
    if isinstance(valor, list):
        return [_sin_numeros_inventados(v, permitidos, fuente) for v in valor]
    if isinstance(valor, dict):
        return {k: (v if k in CAMPOS_SIN_GUARDIA else _sin_numeros_inventados(v, permitidos, fuente))
                for k, v in valor.items()}
    return valor


# los nombres propios de la respuesta tienen que estar en el pedido (2026-10-23: "Old Trafford" para un
# partido de visitante, "la sensacion del entrenamiento"...). Estas palabras con mayuscula son comunes:
CAMPOS_SIN_GUARDIA = {"autor", "tono"}  # el @usuario de un comentario es inventado a proposito
NOMBRES_COMUNES = {
    "instagram", "tiktok", "twitter", "youtube", "twitch", "champions", "premier", "league", "liga", "copa", "mundial",
    "europa", "balon", "bota", "golden", "best", "fifa", "uefa", "var", "mister", "dios", "simon", "mama", "papa",
    "seleccion", "hat", "trick", "vamos", "aguante", "ojo", "atentos", "exclusivo", "ultimo", "ultima", "here",
}
ALIAS = {"man utd": "manchester united red devils", "man city": "citizens", "manchester city": "citizens"}
_NOMBRE_PROPIO = re.compile(r"(?<![#@\w])([A-ZÁÉÍÓÚÑ][a-záéíóúñü]{3,}(?:\s+[A-ZÁÉÍÓÚÑ][a-záéíóúñü]{2,})*)")


def _normal(texto: str) -> str:
    import unicodedata

    sin = "".join(c for c in unicodedata.normalize("NFD", texto.lower()) if unicodedata.category(c) != "Mn")
    return re.sub(r"[^a-z0-9 ]+", " ", sin)


def preparar_fuente(texto: str) -> str:
    """El pedido normalizado, con los apodos de los clubes que nombra (para `nombres_inventados`)."""
    fuente = _normal(texto)
    return fuente + " " + " ".join(apodos for club, apodos in ALIAS.items() if club in fuente)


HECHOS_QUE_NO_SE_INVENTAN = ("entrenamiento", "estadio", "lesion", "penal", "tiro libre", "de cabeza",
                             "capitan", "brazalete", "expulsa", "tarjeta roja", "asistencia", "record")
# nacionalidades: "el uruguayo de La Cruz" (es chileno); vale si el pedido nombra el pais o el gentilicio
GENTILICIOS = ("urugua", "argentin", "chilen", "brasil", "espanol", "italian", "frances", "ingles", "aleman",
               "portugu", "holandes", "colombian", "mexican", "peruan", "venezolan", "ecuatorian", "paraguay",
               "bolivian", "belga", "croata", "noruego", "polaco", "estadounidense", "japones", "coreano")


def nombres_inventados(texto: str, fuente: str) -> list:
    """Los nombres propios del texto que no aparecen en el pedido. Las mayusculas de principio de oracion no
    cuentan (\"Que partido\"), las palabras comunes tampoco."""
    raros = []
    for coincidencia in _NOMBRE_PROPIO.finditer(texto):
        antes = texto[:coincidencia.start()].rstrip(" \"'«¡¿(")
        if not antes or antes[-1] in ".!?:;\n":
            continue  # principio de oracion
        for palabra in _normal(coincidencia.group(1)).split():
            if palabra not in NOMBRES_COMUNES and len(palabra) >= 4 and palabra not in fuente:
                raros.append(palabra)
    normal = _normal(texto)
    raros += [hecho for hecho in HECHOS_QUE_NO_SE_INVENTAN if hecho in normal and hecho not in fuente]
    raros += [g for g in GENTILICIOS if re.search(rf"\b{g}", normal) and g[:5] not in fuente]
    return raros


def pedir_json(prompt_sistema: str, prompt_usuario: str, esquema_ejemplo: dict,
               timeout: float = TIMEOUT, jugador: Optional[int] = None) -> Optional[dict]:
    """El JSON que devolvio el primer proveedor que contesto, o None (sin
    claves, sin internet, sin cuota, desactivada). Nunca lanza. Con `jugador`,
    el pedido lleva la memoria del roleplay. Los textos con numeros que no
    estan en el pedido vuelven vacios (el que llama usa lo del motor local)."""
    try:
        if desactivada():
            return None
        if jugador:
            from roleplay.servicios.memoria import cronica

            memoria = cronica(jugador)
            if memoria:
                prompt_usuario = f"MEMORIA DEL ROLEPLAY (lo que ya paso):\n{memoria}\n\nLO DE AHORA:\n{prompt_usuario}"
                prompt_sistema = f"{prompt_sistema}\n\n{VOZ}"
        sistema = (f"{prompt_sistema}\n\n{REGLAS}\nForma exacta del JSON (mismas claves y tipos): "
                   f"{json.dumps(esquema_ejemplo, ensure_ascii=False)}")
        permitidos = _numeros_de(prompt_usuario)  # (los ejemplos de las consignas no cuentan: no se copian)
        fuente = preparar_fuente(prompt_usuario)
        limite = time.monotonic() + timeout * TOPE_TOTAL
        for proveedor, modelos, llamar in PROVEEDORES:
            for clave in claves(proveedor):
                pendientes, borrados, descubiertos = list(modelos), 0, False
                while pendientes:
                    modelo = pendientes.pop(0)
                    queda = limite - time.monotonic()
                    if queda <= 0.3:
                        return None
                    inicio = time.monotonic()
                    try:
                        datos = llamar(clave, modelo, sistema, prompt_usuario, min(timeout, queda))
                    except _Fallo as fallo:
                        if fallo.otra_clave:
                            break  # esta clave no sirve: la siguiente
                        borrados += fallo.no_existe
                        if proveedor == "groq" and not pendientes and not descubiertos and borrados == len(modelos):
                            descubiertos = True  # Groq dio de baja todos los nuestros: los que tenga hoy
                            pendientes = [m for m in modelos_de_groq(clave, min(timeout, queda)) if m not in modelos]
                        continue  # cuota, caida o respuesta rara: el siguiente modelo
                    ultimo.update(proveedor=proveedor, modelo=modelo, ms=round((time.monotonic() - inicio) * 1000))
                    return _sin_numeros_inventados(datos, permitidos, fuente)
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
