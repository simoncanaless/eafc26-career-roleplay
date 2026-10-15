"""
Motor narrativo local: arma los textos de la app (preguntas, reacciones,
noticias, comentarios, posts, historias) combinando bloques de los corpus
de roleplay/datos/corpus_*.json. Sin IA, sin internet y al instante.

Gramatica: cada corpus es {simbolo: [alternativas]}. Una alternativa es un
texto con {variables} (las pone quien pide el texto) y #otro_simbolo# (se
expande, recursivo). Una alternativa solo entra si tiene todas sus
variables: asi un mismo simbolo sirve con y sin un dato (con el precio del
auto, una frase; sin el, otra).

Cola anti-repeticion (estado_json.narrador_usados):
- por simbolo, los ultimos bloques usados (hasta MEMORIA, y nunca todos: siempre
  queda al menos uno libre) no vuelven a salir hasta que se usen los demas;
- y los ultimos MEMORIA textos completos (su huella): si sale uno igual a uno
  reciente, se vuelve a armar (sorteando las piezas, hasta INTENTOS_TEXTO_NUEVO).
Con eso, en dos partidos seguidos no se lee la misma pregunta ni la misma
estructura mientras el corpus tenga otra opcion.
"""

import hashlib
import json
import random
import re
from contextlib import contextmanager
from functools import lru_cache
from pathlib import Path
from typing import Iterator, Optional

CARPETA_DATOS = Path(__file__).resolve().parent.parent / "datos"
MEMORIA = 40  # bloques por simbolo y textos completos que se recuerdan
PROFUNDIDAD_MAXIMA = 12
INTENTOS_TEXTO_NUEVO = 12

_VARIABLE = re.compile(r"\{(\w+)\}")
_SIMBOLO = re.compile(r"#(\w+)#")


@lru_cache(maxsize=None)
def corpus(nombre: str) -> dict:
    """roleplay/datos/corpus_<nombre>.json (o <nombre>.json)."""
    ruta = CARPETA_DATOS / f"corpus_{nombre}.json"
    if not ruta.exists():
        ruta = CARPETA_DATOS / f"{nombre}.json"
    with ruta.open(encoding="utf-8") as archivo:
        return {clave: valor for clave, valor in json.load(archivo).items() if not clave.startswith("_")}


def huella(texto: str) -> str:
    return hashlib.sha1(texto.lower().encode("utf-8")).hexdigest()[:12]


def limpiar(texto: str) -> str:
    texto = re.sub(r"\s+", " ", texto).strip()
    texto = re.sub(r"\s+([,.;:!?»])", r"\1", texto)
    texto = re.sub(r"([«¿¡])\s+", r"\1", texto)
    texto = re.sub(r"(?<!\.)\.\.(?!\.)", ".", texto)
    # mayuscula despues de un punto (las piezas se juntan en minuscula)
    texto = re.sub(r"([.!?]\s+[¿¡«]?)([a-zà-ü])", lambda m: m.group(1) + m.group(2).upper(), texto)
    if texto:
        i = next((n for n, c in enumerate(texto) if c.isalpha()), None)
        if i is not None:
            texto = texto[:i] + texto[i].upper() + texto[i + 1:]
    return texto


class Narrador:
    """Arma textos con la gramatica de uno o mas corpus. `usados` es la
    memoria anti-repeticion (se modifica en el lugar); `dado`, el azar (las
    pruebas le pasan uno con semilla)."""

    def __init__(self, *nombres: str, usados: Optional[dict] = None, dado: Optional[random.Random] = None,
                 ricas: bool = False):
        self.ricas = ricas  # preferir las alternativas que usan mas datos (el backstory)
        self.gramatica: dict = {}
        for nombre in nombres:
            self.gramatica.update(corpus(nombre))
        self.usados = usados if usados is not None else {}
        self.usados.setdefault("bloques", {})
        self.usados.setdefault("textos", [])
        self.dado = dado or random.Random()
        self._al_azar = False  # en un reintento (ver decir)

    def tiene(self, simbolo: str) -> bool:
        return simbolo in self.gramatica

    def puede(self, simbolo: str, **datos) -> bool:
        """Si hay alguna alternativa de `simbolo` con todos sus datos."""
        return bool(self._candidatas(simbolo, datos))

    def decir(self, simbolo: str, **datos) -> str:
        """Un texto nuevo (que no sea igual a uno de los ultimos)."""
        texto = ""
        try:
            for intento in range(INTENTOS_TEXTO_NUEVO):
                # si salio uno reciente, se sortea entre todas las piezas: con
                # la rueda de bloques, dos piezas de dos opciones rotan en fila
                # y vuelven a dar los mismos dos textos una y otra vez
                self._al_azar = intento > 0
                texto = limpiar(self._expandir(simbolo, datos, 0))
                if not self.reciente(texto):
                    break
        finally:
            self._al_azar = False
        self.anotar(texto)
        return texto

    def reciente(self, texto: str) -> bool:
        return huella(texto) in self.usados["textos"]

    def anotar(self, texto: str) -> None:
        """Recuerda un texto completo (armado con varias piezas) para no repetirlo."""
        if texto:
            self.usados["textos"].append(huella(texto))
            del self.usados["textos"][:-MEMORIA]

    def elegir(self, simbolo: str, **datos) -> str:
        """Como decir, pero sin anotar el texto completo (para piezas que
        despues se juntan en un texto mas grande)."""
        return limpiar(self._expandir(simbolo, datos, 0))

    # ---- la gramatica ----

    def _completa(self, alternativa: str, datos: dict, profundidad: int) -> bool:
        if any(datos.get(v) in (None, "") for v in _VARIABLE.findall(alternativa)):
            return False
        if profundidad >= PROFUNDIDAD_MAXIMA:
            return not _SIMBOLO.search(alternativa)
        return all(s in self.gramatica for s in _SIMBOLO.findall(alternativa))

    def _candidatas(self, simbolo: str, datos: dict, profundidad: int = 0) -> list[tuple[int, str]]:
        return [(i, a) for i, a in enumerate(self.gramatica.get(simbolo, [])) if self._completa(a, datos, profundidad)]

    def _expandir(self, simbolo: str, datos: dict, profundidad: int) -> str:
        candidatas = self._candidatas(simbolo, datos, profundidad)
        if not candidatas:
            return ""
        if self.ricas:
            mas_datos = max(len(set(_VARIABLE.findall(a))) for _, a in candidatas)
            candidatas = [c for c in candidatas if len(set(_VARIABLE.findall(c[1]))) == mas_datos]
        recientes = self.usados["bloques"].setdefault(simbolo, [])
        frescas = [c for c in candidatas if c[0] not in recientes]
        if self._al_azar:
            indice, alternativa = self.dado.choice(candidatas)
        elif frescas:
            indice, alternativa = self.dado.choice(frescas)
        else:  # todas usadas hace poco: la menos reciente
            indice, alternativa = min(candidatas, key=lambda c: recientes.index(c[0]))
        if indice in recientes:
            recientes.remove(indice)
        recientes.append(indice)
        # nunca se bloquean todas: siempre queda al menos una libre
        tope = max(0, min(MEMORIA, len(self.gramatica[simbolo]) - 1))
        del recientes[: max(0, len(recientes) - tope)]
        texto = _SIMBOLO.sub(lambda m: self._expandir(m.group(1), datos, profundidad + 1), alternativa)
        return _VARIABLE.sub(lambda m: str(datos[m.group(1)]), texto)


@contextmanager
def narrador(player_id: Optional[int], *nombres: str, dado: Optional[random.Random] = None) -> Iterator[Narrador]:
    """Un Narrador con la memoria anti-repeticion del jugador, que se guarda
    al terminar. Sin jugador (ej. el backstory antes de crearlo), sin memoria."""
    from roleplay import database

    usados = database.get_narrador_usados(player_id) if player_id else {}
    escritor = Narrador(*nombres, usados=usados, dado=dado)
    yield escritor
    if player_id:
        try:
            database.set_narrador_usados(player_id, escritor.usados)
        except ValueError:  # el perfil ya no existe (o todavia no): el texto sale igual, sin memoria
            pass


def unir(*partes: str) -> str:
    """Junta oraciones, sin dobles espacios ni partes vacias."""
    return limpiar(" ".join(p.strip() for p in partes if p and p.strip()))
