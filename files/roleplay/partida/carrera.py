"""
El mundo de la carrera a partir de los registros del guardado: equipos,
competiciones, partidos, quien jugo y marco en cada uno, tablas y
estadisticas. Todo es calculo deterministico; la IA solo pone nombres a
los jugadores que la partida no trae (ver servicios/identificar.py).
"""

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Optional

from roleplay.partida import formato
from roleplay.partida.formato import FormatoDesconocido

# Codigos de FC 26, identificados por contenido (docs/partida-fc26.md). Los
# nombres "de verdad" estan en el fifa_ng_db-meta.xml de EA, que no se usa.
T_EQUIPOS, C_EQUIPO_ID, C_EQUIPO_NOMBRE = "lyxL", "mCXg", "AUsv"  # id + 1
T_JUGADORES, C_JUGADOR_ID, C_NACIMIENTO = "CZUM", "ykFq", "WVIU"  # dias desde 1582-10-14
T_VINCULOS, C_VINCULO_EQUIPO, C_VINCULO_POSICION = "RrqT", "mCXg", "vjla"  # equipo + 1
T_LIGAS, C_LIGA_ID, C_LIGA_NOMBRE = "onMQ", "aQrQ", "HEQX"  # id + 1
T_NOMBRES_EDITADOS, C_NOMBRE, C_APODO, C_APELLIDO = "nQVU", "HdeP", "xnfZ", "rREd"
T_USUARIO = "mPrV"  # el jugador de la carrera: mismos campos de nombre
TABLAS_MUNDO = {T_EQUIPOS, T_JUGADORES, T_VINCULOS, T_LIGAS, T_NOMBRES_EDITADOS}

ORIGEN_FECHAS = date(1582, 10, 14)

POSICIONES = {
    0: "arquero", 1: "libero", 2: "carrilero derecho", 3: "lateral derecho", 4: "defensa central",
    5: "defensa central", 6: "defensa central", 7: "lateral izquierdo", 8: "carrilero izquierdo",
    9: "mediocentro defensivo", 10: "mediocentro defensivo", 11: "mediocentro defensivo",
    12: "volante derecho", 13: "mediocentro", 14: "mediocentro", 15: "mediocentro",
    16: "volante izquierdo", 17: "mediapunta", 18: "mediapunta", 19: "mediapunta",
    20: "segundo delantero", 21: "segundo delantero", 22: "segundo delantero", 23: "extremo derecho",
    24: "delantero centro", 25: "delantero centro", 26: "delantero centro", 27: "extremo izquierdo",
    28: "suplente", 29: "reserva",
}


def _fecha(aaaammdd: int) -> date:
    return date(aaaammdd // 10000, aaaammdd // 100 % 100, aaaammdd % 100)


@dataclass(frozen=True)
class Partido:
    fecha: date
    competicion: int
    local: int
    visita: int
    goles_local: Optional[int]
    goles_visita: Optional[int]
    jugado: bool

    def participa(self, equipo: int) -> bool:
        return equipo in (self.local, self.visita)

    def rival(self, equipo: int) -> int:
        return self.visita if equipo == self.local else self.local

    def goles_de(self, equipo: int) -> Optional[int]:
        return self.goles_local if equipo == self.local else self.goles_visita

    def goles_contra(self, equipo: int) -> Optional[int]:
        return self.goles_visita if equipo == self.local else self.goles_local

    def resultado_para(self, equipo: int) -> Optional[str]:
        if not self.jugado:
            return None
        a_favor, en_contra = self.goles_de(equipo), self.goles_contra(equipo)
        return "victoria" if a_favor > en_contra else "derrota" if a_favor < en_contra else "empate"


@dataclass(frozen=True)
class Actuacion:
    """Un jugador en un partido: sale de sus ultimos 5 partidos guardados."""

    jugador: int
    equipo: int
    competicion: int
    fecha: date
    minutos: int
    nota: Optional[float]
    goles: int


@dataclass(frozen=True)
class Estadistica:
    """Totales de un jugador en un equipo y una competicion."""

    jugador: int
    equipo: int
    competicion: int
    partidos: int
    minutos: int
    goles: int
    asistencias: int
    amarillas: int
    rojas: int
    figura: int
    nota_total: int  # decimas

    @property
    def nota_promedio(self) -> Optional[float]:
        return round(self.nota_total / self.partidos / 10, 2) if self.partidos else None


@dataclass(frozen=True)
class FilaPosiciones:
    equipo: int
    pj: int = 0
    pg: int = 0
    pe: int = 0
    pp: int = 0
    gf: int = 0
    gc: int = 0

    @property
    def pts(self) -> int:
        return 3 * self.pg + self.pe

    @property
    def dif(self) -> int:
        return self.gf - self.gc


@dataclass(frozen=True)
class Competicion:
    id: int
    codigo: str
    nombre: Optional[str]  # None si la partida no lo trae (copas): lo pone la IA
    es_liga: bool
    continental: bool


@dataclass
class Carrera:
    partida: str
    archivo: str
    guardada_en: datetime
    equipos: dict[int, str]
    competiciones: dict[int, Competicion]
    partidos: list[Partido]
    estadisticas: list[Estadistica]
    actuaciones: list[Actuacion]
    nacimientos: dict[int, date]
    vinculos: dict[int, list[tuple[int, int]]]  # jugador -> [(equipo, posicion)]
    nombres_editados: dict[int, str]
    usuario_id: Optional[int]
    clubes: set[int] = field(default_factory=set)

    # ---- tiempo ----

    def fecha_actual(self) -> Optional[date]:
        jugados = [p.fecha for p in self.partidos if p.jugado]
        return max(jugados) if jugados else None

    # ---- nombres ----

    def equipo(self, equipo_id: Optional[int]) -> str:
        return self.equipos.get(equipo_id, f"equipo {equipo_id}")

    def competicion(self, competicion_id: int) -> str:
        c = self.competiciones.get(competicion_id)
        if c and c.nombre:
            return c.nombre
        if c and c.continental:
            return "torneo continental"
        return "copa" if c and not c.es_liga else "competicion"

    # ---- el usuario ----

    def equipo_usuario(self) -> Optional[int]:
        """El club del jugador del usuario: el de su actuacion mas reciente
        en un club (no en la seleccion)."""
        if self.usuario_id is None:
            return None
        suyas = [a for a in self.actuaciones if a.jugador == self.usuario_id and a.equipo in self.clubes]
        if suyas:
            return max(suyas, key=lambda a: a.fecha).equipo
        for equipo, _ in self.vinculos.get(self.usuario_id, []):
            if equipo in self.clubes:
                return equipo
        return None

    def estadisticas_de(self, jugador: int) -> list[Estadistica]:
        return [e for e in self.estadisticas if e.jugador == jugador and e.partidos]

    # ---- partidos ----

    def partidos_de(self, equipo: int, jugados: Optional[bool] = None) -> list[Partido]:
        return sorted(
            (p for p in self.partidos if p.participa(equipo) and (jugados is None or p.jugado == jugados)),
            key=lambda p: p.fecha,
        )

    def ultimo_partido_de(self, equipo: int) -> Optional[Partido]:
        jugados = self.partidos_de(equipo, jugados=True)
        return jugados[-1] if jugados else None

    def proximo_partido_de(self, equipo: int) -> Optional[Partido]:
        pendientes = self.partidos_de(equipo, jugados=False)
        return pendientes[0] if pendientes else None

    def actuaciones_en(self, partido: Partido) -> list[Actuacion]:
        return sorted(
            (
                a for a in self.actuaciones
                if a.fecha == partido.fecha and a.competicion == partido.competicion and partido.participa(a.equipo)
            ),
            key=lambda a: (-a.goles, -(a.nota or 0)),
        )

    # ---- tablas y rankings ----

    def tabla(self, competicion: int) -> list[FilaPosiciones]:
        """Tabla calculada con los partidos jugados (la que trae la partida
        no siempre esta al dia). Solo tiene sentido para ligas."""
        filas: dict[int, dict] = defaultdict(lambda: defaultdict(int))
        for p in self.partidos:
            if p.competicion != competicion:
                continue
            for equipo in (p.local, p.visita):
                filas[equipo]["pj"] += 0  # aparece aunque no haya jugado
            if not p.jugado:
                continue
            for equipo in (p.local, p.visita):
                fila = filas[equipo]
                fila["pj"] += 1
                fila["gf"] += p.goles_de(equipo)
                fila["gc"] += p.goles_contra(equipo)
                resultado = p.resultado_para(equipo)
                fila["pg" if resultado == "victoria" else "pe" if resultado == "empate" else "pp"] += 1
        tabla = [FilaPosiciones(equipo, **dict(valores)) for equipo, valores in filas.items()]
        return sorted(tabla, key=lambda f: (-f.pts, -f.dif, -f.gf, self.equipo(f.equipo)))

    def posicion_en(self, competicion: int, equipo: int) -> Optional[int]:
        for numero, fila in enumerate(self.tabla(competicion), start=1):
            if fila.equipo == equipo:
                return numero
        return None

    def goleadores(self, competicion: int, cantidad: int = 10) -> list[Estadistica]:
        de_la_competicion = [e for e in self.estadisticas if e.competicion == competicion and e.goles]
        return sorted(de_la_competicion, key=lambda e: (-e.goles, e.partidos))[:cantidad]

    # ---- para reconocer jugadores ----

    def nombre_editado(self, jugador: int) -> Optional[str]:
        return self.nombres_editados.get(jugador)

    def ficha(self, jugador: int) -> dict:
        """Lo que la partida sabe de un jugador, para que la IA lo reconozca."""
        ficha = {"id": jugador}
        club = next((e for e, _ in self.vinculos.get(jugador, []) if e in self.clubes), None)
        posicion = next((p for e, p in self.vinculos.get(jugador, []) if e == club), None)
        seleccion = next((e for e, _ in self.vinculos.get(jugador, []) if e not in self.clubes), None)
        if club is None:
            club = next((a.equipo for a in self.actuaciones if a.jugador == jugador), None)
        if club is not None:
            ficha["club"] = self.equipo(club)
        if posicion is not None and posicion in POSICIONES and posicion < 28:
            ficha["posicion"] = POSICIONES[posicion]
        if seleccion is not None:
            ficha["seleccion"] = self.equipo(seleccion)
        nacimiento = self.nacimientos.get(jugador)
        hoy = self.fecha_actual()
        if nacimiento:
            ficha["nacimiento"] = nacimiento.isoformat()
            if hoy:
                ficha["edad"] = (hoy - nacimiento).days // 365
        goles = sum(e.goles for e in self.estadisticas_de(jugador))
        if goles:
            ficha["goles_en_la_temporada"] = goles
        return ficha


# ---- armar la carrera desde los bytes ----


def _nombre_completo(fila: dict) -> str:
    apodo = (fila.get(C_APODO) or "").strip()
    if apodo:
        return apodo
    return " ".join(p for p in ((fila.get(C_NOMBRE) or "").strip(), (fila.get(C_APELLIDO) or "").strip()) if p)


def construir(datos: bytes, archivo: str = "", guardada_en: Optional[datetime] = None) -> Carrera:
    partida = formato.nombre_partida(datos)
    mundo = formato.leer_tablas(datos, formato.base_con_tabla(datos, T_EQUIPOS), TABLAS_MUNDO)
    faltan = TABLAS_MUNDO - set(mundo)
    if faltan:
        raise FormatoDesconocido(f"Faltan tablas en el guardado: {sorted(faltan)}")
    base_carrera = formato.base_con_tabla(datos, T_USUARIO)
    usuario = formato.leer_tablas(datos, base_carrera, {T_USUARIO})[T_USUARIO].registros

    equipos = {f[C_EQUIPO_ID] + 1: f[C_EQUIPO_NOMBRE] for f in mundo[T_EQUIPOS].registros}
    nombres_ligas = {f[C_LIGA_ID] + 1: f[C_LIGA_NOMBRE] for f in mundo[T_LIGAS].registros}
    nacimientos = {}
    for f in mundo[T_JUGADORES].registros:
        dias = f.get(C_NACIMIENTO)
        if dias:
            nacimientos[f[C_JUGADOR_ID]] = ORIGEN_FECHAS + timedelta(days=dias)
    vinculos: dict[int, list] = defaultdict(list)
    for f in mundo[T_VINCULOS].registros:
        vinculos[f[C_JUGADOR_ID]].append((f[C_VINCULO_EQUIPO] + 1, f[C_VINCULO_POSICION]))
    nombres_editados = {f[C_JUGADOR_ID]: _nombre_completo(f) for f in mundo[T_NOMBRES_EDITADOS].registros}

    usuario_id = None
    if usuario:
        buscado = _nombre_completo(usuario[0])
        candidatos = [jugador for jugador, nombre in nombres_editados.items() if nombre == buscado]
        usuario_id = candidatos[-1] if candidatos else None

    limites = formato.secciones(datos)
    filas = formato.leer_filas_de_tabla(datos, *formato.seccion(limites, "stagadv"))
    registros_partido = formato.leer_partidos(datos, *formato.seccion(limites, "teams"), filas)
    if not registros_partido:
        raise FormatoDesconocido("El guardado no tiene partidos que se puedan leer.")
    estadisticas_crudas = formato.leer_estadisticas(datos, *formato.seccion(limites, "stndgs"))
    inicio_comp, fin_comp = limites.get("compavg", (0, len(datos)))
    competiciones_crudas = formato.leer_competiciones(datos, inicio_comp, fin_comp) or formato.leer_competiciones(datos)

    partidos = [
        Partido(
            _fecha(r.fecha), r.competicion, filas[r.fila_local].equipo, filas[r.fila_visita].equipo,
            r.goles_local if r.jugado else None, r.goles_visita if r.jugado else None, r.jugado,
        )
        for r in registros_partido
        if filas[r.fila_local].equipo is not None and filas[r.fila_visita].equipo is not None
    ]

    def es_continental(competicion_id: int) -> bool:
        visto, actual = set(), competiciones_crudas.get(competicion_id)
        while actual and actual.padre is not None and actual.padre not in visto:
            visto.add(actual.padre)
            actual = competiciones_crudas.get(actual.padre)
            if actual and actual.nivel == 2:
                return False
            if actual and actual.nivel == 1:
                return True
        return False

    competiciones = {}
    for competicion_id in {p.competicion for p in partidos}:
        cruda = competiciones_crudas.get(competicion_id)
        codigo = cruda.codigo if cruda else ""
        liga = int(codigo[1:]) if codigo[:1] == "C" and codigo[1:].isdigit() else None
        nombre = nombres_ligas.get(liga) if liga is not None else None
        competiciones[competicion_id] = Competicion(
            competicion_id, codigo, nombre, es_liga=nombre is not None, continental=es_continental(competicion_id)
        )
    clubes = {
        equipo
        for p in partidos
        if competiciones[p.competicion].es_liga
        for equipo in (p.local, p.visita)
    }

    estadisticas, actuaciones, vistas = [], [], set()
    for r in estadisticas_crudas:
        estadisticas.append(
            Estadistica(
                r.jugador, r.equipo, r.competicion, r.partidos, r.minutos, r.goles,
                r.asistencias, r.amarillas, r.rojas, r.figura, r.nota_total,
            )
        )
        for u in r.ultimos:
            clave = (r.jugador, r.competicion, u.fecha)
            if u.minutos and clave not in vistas:
                vistas.add(clave)
                actuaciones.append(Actuacion(r.jugador, r.equipo, r.competicion, _fecha(u.fecha), u.minutos, u.nota, u.goles))

    return Carrera(
        partida=partida,
        archivo=archivo,
        guardada_en=guardada_en or datetime.now(),
        equipos=equipos,
        competiciones=competiciones,
        partidos=partidos,
        estadisticas=estadisticas,
        actuaciones=actuaciones,
        nacimientos=nacimientos,
        vinculos=dict(vinculos),
        nombres_editados=nombres_editados,
        usuario_id=usuario_id,
        clubes=clubes,
    )
