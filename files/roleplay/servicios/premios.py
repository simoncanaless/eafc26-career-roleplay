"""
Los premios con su nombre de verdad y la gala de fin de temporada.

- `nombre_premio(tipo, liga)`: cada liga llama a sus premios a su manera (el
  jugador del mes de la Premier, el Pichichi de LALIGA, el Capocannoniere de
  la Serie A, la Bola de Prata de Portugal...). Sin la liga en la lista, uno
  generico ("Jugador del mes de la <liga>").
- `gala(carrera)`: los premios globales, que el juego no entrega de forma
  legible: Balon de Oro, Trofeo Kopa y Trofeo Gerd Muller (France Football),
  The Best (FIFA), Golden Boy (Tuttosport) y la Bota de Oro europea (ESM). Los
  decide el CODIGO con los numeros reales de la temporada de TODOS los
  jugadores de la partida (goles, asistencias, nota, titulos de su club, liga,
  edad y media): nada se inventa, es la votacion de este mundo. La corre
  servicios/partida_real.py cuando termina la liga del usuario (una vez por
  temporada).
"""

import unicodedata
from collections import defaultdict
from dataclasses import dataclass
from typing import Optional

# ---- los nombres por liga ----

# clave: un pedazo del nombre de la liga como lo trae el juego (sin tildes, en minuscula)
POR_LIGA = {
    "premier league": {"jugador_del_mes": "Jugador del Mes de la Premier League",
                       "maximo_goleador": "Bota de Oro de la Premier League",
                       "campeon": "Campeon de la Premier League"},
    "laliga": {"jugador_del_mes": "Jugador del Mes de LALIGA", "maximo_goleador": "Trofeo Pichichi",
               "campeon": "Campeon de LALIGA"},
    "serie a": {"jugador_del_mes": "MVP del Mes de la Serie A", "maximo_goleador": "Capocannoniere de la Serie A",
                "campeon": "Scudetto"},
    "serie b": {"jugador_del_mes": "Jugador del Mes de la Serie B", "maximo_goleador": "Capocannoniere de la Serie B",
                "campeon": "Campeon de la Serie B"},
    "bundesliga": {"jugador_del_mes": "Spieler des Monats de la Bundesliga",
                   "maximo_goleador": "Torjaegerkanone (maximo goleador de la Bundesliga)",
                   "campeon": "Meisterschale (campeon de la Bundesliga)"},
    "ligue 1": {"jugador_del_mes": "Jugador del Mes UNFP", "maximo_goleador": "Maximo goleador de la Ligue 1",
                "campeon": "Campeon de la Ligue 1"},
    "championship": {"jugador_del_mes": "Jugador del Mes de la EFL Championship",
                     "maximo_goleador": "Bota de Oro de la EFL Championship",
                     "campeon": "Campeon de la EFL Championship"},
    "eredivisie": {"jugador_del_mes": "Speler van de Maand de la Eredivisie",
                   "maximo_goleador": "Maximo goleador de la Eredivisie", "campeon": "Campeon de la Eredivisie"},
    "liga portugal": {"jugador_del_mes": "Jogador do Mes de la Liga Portugal", "maximo_goleador": "Bola de Prata",
                      "campeon": "Campeon de la Liga Portugal"},
    "mls": {"jugador_del_mes": "Jugador del Mes de la MLS", "maximo_goleador": "Bota de Oro de la MLS",
            "campeon": "Campeon de la MLS"},
    "saudi": {"jugador_del_mes": "Jugador del Mes de la Roshn Saudi League",
              "maximo_goleador": "Maximo goleador de la Roshn Saudi League", "campeon": "Campeon de la Saudi League"},
}
GENERICOS = {"jugador_del_mes": "Jugador del Mes de la {liga}", "maximo_goleador": "Maximo goleador de la {liga}",
             "campeon": "Campeon de la {liga}"}


def normalizar(texto: str) -> str:
    sin_tildes = unicodedata.normalize("NFKD", texto or "").encode("ascii", "ignore").decode()
    return " ".join(sin_tildes.lower().split())


def nombres_de(liga: str) -> dict:
    clave = normalizar(liga)
    return next((v for k, v in POR_LIGA.items() if k in clave), {})


def nombre_premio(tipo: str, liga: str) -> str:
    propio = nombres_de(liga).get(tipo)
    if propio:
        return propio
    generico = GENERICOS.get(tipo)
    return generico.format(liga=liga) if generico and liga else (generico or tipo).replace(" de la {liga}", "")


# ---- la gala de fin de temporada ----

TOP5 = ("premier league", "laliga", "serie a", "bundesliga", "ligue 1")
SEGUNDAS = ("championship", "serie b", "2. bundesliga", "ligue 2", "hypermotion", "segunda")
MINIMO_PARTIDOS = 15
SUB = 21  # Kopa y Golden Boy
NOMINADOS = 30


@dataclass(frozen=True)
class Premio:
    id: str
    nombre: str
    quien: str  # quien lo entrega
    reputacion: int  # lo que suma al usuario si lo gana


PREMIOS = {
    "balon_de_oro": Premio("balon_de_oro", "Balon de Oro", "France Football", 15),
    "the_best": Premio("the_best", "The Best", "FIFA", 12),
    "kopa": Premio("kopa", "Trofeo Kopa", "France Football", 8),
    "golden_boy": Premio("golden_boy", "Golden Boy", "Tuttosport", 8),
    "gerd_muller": Premio("gerd_muller", "Trofeo Gerd Muller", "France Football", 8),
    "bota_de_oro": Premio("bota_de_oro", "Bota de Oro europea", "ESM", 8),
}


@dataclass
class Candidato:
    jugador: int
    equipo: int
    liga: str
    partidos: int = 0
    goles: int = 0
    goles_liga: int = 0
    asistencias: int = 0
    nota_total: int = 0
    titulos: int = 0  # puntos por titulos de su club
    edad: Optional[int] = None
    media: int = 0

    @property
    def nota(self) -> float:
        return self.nota_total / self.partidos / 10 if self.partidos else 0.0

    def peso_liga(self) -> float:
        clave = normalizar(self.liga)
        if any(k in clave for k in SEGUNDAS):
            return 0.4
        return 1.0 if any(k in clave for k in TOP5) else 0.7

    def coeficiente_bota(self) -> float:
        """Coeficiente de la Bota de Oro europea (ESM): x2 en las 5 grandes, x1,5 el resto de Europa."""
        clave = normalizar(self.liga)
        if any(k in clave for k in SEGUNDAS):
            return 1.0
        return 2.0 if any(k in clave for k in TOP5) else 1.5

    def puntaje(self, nota_pesa: float = 3.0) -> float:
        rendimiento = (self.goles + 0.6 * self.asistencias) * self.peso_liga()
        return (rendimiento + nota_pesa * (self.nota - 7) * min(self.partidos, 40) / 10 + self.titulos
                + 0.8 * (self.media - 80))


def campeones(carrera) -> dict[int, int]:
    """equipo -> puntos de titulos de la temporada: liga terminada primero (12), torneo continental (15) y copa (5).
    Una copa o un torneo continental se da por ganado con el ultimo partido jugado sin pendientes (la final)."""
    from roleplay.servicios.partida_real import liga_terminada

    puntos: dict[int, int] = defaultdict(int)
    for competicion_id, competicion in carrera.competiciones.items():
        if competicion.es_liga:
            if liga_terminada(carrera, competicion_id):
                tabla = carrera.tabla(competicion_id)
                if tabla:
                    puntos[tabla[0].equipo] += 12
            continue
        partidos = [p for p in carrera.partidos if p.competicion == competicion_id]
        if not partidos or any(not p.jugado for p in partidos):
            continue
        final = max(partidos, key=lambda p: p.fecha)
        if final.goles_local != final.goles_visita:
            ganador = final.local if final.goles_local > final.goles_visita else final.visita
            puntos[ganador] += 15 if competicion.continental else 5
    return puntos


def candidatos(carrera) -> list[Candidato]:
    hoy = carrera.fecha_actual()
    titulos = campeones(carrera)
    por_jugador: dict[int, Candidato] = {}
    partidos_en: dict[tuple, int] = defaultdict(int)
    for e in carrera.estadisticas:
        if e.jugador in carrera.mujeres or not e.partidos:
            continue
        if e.equipo in carrera.clubes:
            partidos_en[(e.jugador, e.equipo)] += e.partidos
        c = por_jugador.setdefault(e.jugador, Candidato(e.jugador, e.equipo, ""))
        c.partidos += e.partidos
        c.goles += e.goles
        c.asistencias += e.asistencias
        c.nota_total += e.nota_total
        if carrera.competiciones.get(e.competicion) and carrera.competiciones[e.competicion].es_liga:
            c.goles_liga += e.goles
    clubes_de: dict[int, dict] = defaultdict(dict)
    for (jugador, equipo), n in partidos_en.items():
        clubes_de[jugador][equipo] = n
    liga_de = {}  # el club -> el nombre de la liga que juega en la partida
    for p in carrera.partidos:
        competicion = carrera.competiciones.get(p.competicion)
        if competicion and competicion.es_liga:
            liga_de.setdefault(p.local, competicion.nombre or "")
            liga_de.setdefault(p.visita, competicion.nombre or "")
    for jugador, c in por_jugador.items():
        if clubes_de.get(jugador):
            c.equipo = max(clubes_de[jugador], key=clubes_de[jugador].get)
        c.liga = liga_de.get(c.equipo, "")
        c.titulos = titulos.get(c.equipo, 0)
        c.media = carrera.medias.get(jugador, 0)
        nacimiento = carrera.nacimientos.get(jugador)
        if nacimiento and hoy:
            c.edad = hoy.year - nacimiento.year - ((hoy.month, hoy.day) < (nacimiento.month, nacimiento.day))
    return [c for c in por_jugador.values() if c.partidos >= MINIMO_PARTIDOS]


@dataclass
class Resultado:
    premio: Premio
    ranking: list[Candidato]

    @property
    def ganador(self) -> Optional[Candidato]:
        return self.ranking[0] if self.ranking else None

    def puesto(self, jugador: Optional[int]) -> Optional[int]:
        return next((i for i, c in enumerate(self.ranking, start=1) if c.jugador == jugador), None)


def gala(carrera) -> list[Resultado]:
    """Los premios globales de la temporada, con su ranking (del mejor al peor)."""
    todos = candidatos(carrera)
    if not todos:
        return []
    jovenes = [c for c in todos if c.edad is not None and c.edad < SUB]

    def orden(lista, clave):
        return sorted(lista, key=lambda c: (clave(c), c.goles, -c.jugador), reverse=True)

    resultados = [
        Resultado(PREMIOS["balon_de_oro"], orden(todos, lambda c: c.puntaje())),
        Resultado(PREMIOS["the_best"], orden(todos, lambda c: c.puntaje(nota_pesa=5.0))),
        Resultado(PREMIOS["gerd_muller"], orden(todos, lambda c: c.goles)),
        Resultado(PREMIOS["bota_de_oro"], orden(todos, lambda c: c.goles_liga * c.coeficiente_bota())),
    ]
    if jovenes:
        resultados.insert(2, Resultado(PREMIOS["kopa"], orden(jovenes, lambda c: c.puntaje())))
        europeos = [c for c in jovenes if "mls" not in normalizar(c.liga) and "saudi" not in normalizar(c.liga)]
        if europeos:
            resultados.insert(3, Resultado(PREMIOS["golden_boy"], orden(europeos, lambda c: c.puntaje())))
    return resultados


def nombre_completo(premio: Premio) -> str:
    return f"{premio.nombre} ({premio.quien})"
