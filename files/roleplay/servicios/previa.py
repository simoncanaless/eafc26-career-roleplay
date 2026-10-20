"""
Conferencia de prensa PREVIA al proximo partido del club. Los datos salen
de la partida de FC 26 (rival, tabla, rachas, si ya se enfrentaron, el
goleador del rival). Las preguntas y la evaluacion son las de la entrevista
post-partido (servicios/entrevista.py): los mismos tres periodistas, el
motor narrativo y el evaluador lexico (y la IA hibrida si esta, igual que
en la entrevista: reescribe sobre los mismos hechos).

No se guarda como partido (no suma partidos ni goles): deja una noticia
con el titular de la conferencia y mueve la reputacion.
"""

from dataclasses import dataclass, field
from typing import Optional

from pydantic import BaseModel

from roleplay.models import NoticiaPrensa, PlayerProfile
from roleplay.partida.carrera import Carrera
from roleplay.servicios import cruce, lexico
from roleplay.servicios.narrador import narrador
from roleplay.servicios.partida_real import (
    clave_partido,
    describir_jugador,
    fecha_corta,
    marcador,
    nombres_de_jugadores,
)

DELTA_REPUTACION_MAXIMO = 10  # una previa pesa menos que lo que pasa en la cancha
RACHA = 5
LETRAS = {"victoria": "G", "empate": "E", "derrota": "P"}


@dataclass
class PreviaPartido:
    clave: str  # clave_partido del proximo partido: para saber si ya se hizo
    club: str
    rival: str
    de_local: bool
    competicion: str
    fecha: str
    datos: list[str] = field(default_factory=list)  # hechos reales para la pantalla
    ya_hecha: bool = False
    # lo mismo, suelto, para las preguntas
    posicion: str = ""
    posicion_rival: str = ""
    racha_club: str = ""
    racha_rival: str = ""
    cruce: str = ""
    goleador: str = ""
    goles_goleador: int = 0
    puesto: int = 0  # en la tabla (0 = no es de liga)
    puesto_rival: int = 0
    puntos: int = 0
    puntos_rival: int = 0

    @property
    def resumen(self) -> str:
        condicion = "de local" if self.de_local else "de visita"
        return f"vs {self.rival} ({condicion}) · {self.competicion} · {self.fecha}"


def _racha(carrera: Carrera, equipo: int) -> str:
    ultimos = carrera.partidos_de(equipo, jugados=True)[-RACHA:]
    return " ".join(LETRAS[p.resultado_para(equipo)] for p in ultimos)


def previa_del_proximo(
    carrera: Carrera, nombres: Optional[dict] = None, estado_partida: Optional[dict] = None
) -> Optional[PreviaPartido]:
    """La previa del proximo partido del club del usuario, o None si no hay
    club o no le queda ningun partido por jugar. Sin `nombres`, los de la
    base local (servicios/identificar.py)."""
    equipo = carrera.equipo_usuario()
    if equipo is None:
        return None
    proximo = carrera.proximo_partido_de(equipo)
    if proximo is None:
        return None
    rival = proximo.rival(equipo)
    club, nombre_rival = carrera.equipo(equipo), carrera.equipo(rival)
    competicion = carrera.competiciones.get(proximo.competicion)
    datos = []
    sueltos = {}

    if competicion and competicion.es_liga:
        tabla = carrera.tabla(proximo.competicion)
        puestos = {f.equipo: (n, f) for n, f in enumerate(tabla, start=1)}
        if equipo in puestos and rival in puestos:
            (p_club, f_club), (p_rival, f_rival) = puestos[equipo], puestos[rival]
            datos.append(
                f"En la tabla: {club} {p_club}° con {f_club.pts} pts, {nombre_rival} {p_rival}° con "
                f"{f_rival.pts} pts (de {len(tabla)} equipos)."
            )
            sueltos.update(posicion=f"{p_club}°", posicion_rival=f"{p_rival}°", puesto=p_club, puesto_rival=p_rival,
                           puntos=f_club.pts, puntos_rival=f_rival.pts)
            if p_rival == len(tabla):
                sueltos["posicion_rival"] = f"{p_rival}° (ultimo)"

    for nombre, id_equipo, clave in ((club, equipo, "racha_club"), (nombre_rival, rival, "racha_rival")):
        racha = _racha(carrera, id_equipo)
        if racha:
            datos.append(f"Racha de {nombre} (ultimos partidos, el mas reciente al final): {racha}.")
            sueltos[clave] = racha.replace(" ", "")

    ultimo_rival = carrera.ultimo_partido_de(rival)
    if ultimo_rival is not None and not ultimo_rival.participa(equipo):
        datos.append(
            f"Ultimo partido de {nombre_rival}: {marcador(carrera, ultimo_rival)} "
            f"({carrera.competicion(ultimo_rival.competicion)})."
        )

    cruces = [p for p in carrera.partidos_de(equipo, jugados=True) if p.participa(rival)]
    if cruces:
        datos.append(
            "Ya se enfrentaron esta temporada: "
            + "; ".join(f"{marcador(carrera, p)} ({carrera.competicion(p.competicion)}, {fecha_corta(p.fecha)})" for p in cruces)
            + "."
        )
        sueltos["cruce"] = marcador(carrera, cruces[-1])

    goleador = next((e for e in carrera.goleadores(proximo.competicion, 200) if e.equipo == rival), None)
    if goleador is not None:
        if nombres is None:
            nombres = nombres_de_jugadores(carrera, {goleador.jugador})
        datos.append(
            f"Goleador de {nombre_rival} ({carrera.competicion(proximo.competicion)}): "
            f"{describir_jugador(carrera, goleador.jugador, nombres)} con {goleador.goles} goles."
        )
        sueltos.update(goleador=describir_jugador(carrera, goleador.jugador, nombres), goles_goleador=goleador.goles)

    clave = clave_partido(proximo)
    return PreviaPartido(
        clave=clave,
        club=club,
        rival=nombre_rival,
        de_local=proximo.local == equipo,
        competicion=carrera.competicion(proximo.competicion),
        fecha=fecha_corta(proximo.fecha),
        datos=datos,
        ya_hecha=(estado_partida or {}).get("previa") == clave,
        **sueltos,
    )


# ---- preguntas y evaluacion (motor narrativo + evaluador lexico) ----


class ReaccionPrevia(BaseModel):
    titular: str
    reaccion_prensa: str
    tono: str = "neutral"
    delta_reputacion: int
    nuevo_gancho_narrativo: str = ""
    eje: str = lexico.NEUTRO
    cita: str = ""
    delta_carino: int = 0


# en la previa no hay resultado: cuanto suma cada eje por si solo
BASE_PREVIA = {"humildad_equipo": 2, "amor_hinchada": 2, "ambicion_foco": 2, "ego_confianza": -1,
               "excusa_polemica": -3, lexico.NEUTRO: 0}
CARINO_PREVIA = {"amor_hinchada": 2, "humildad_equipo": 1, "excusa_polemica": -1}


def generar_previa(perfil: PlayerProfile, previa: PreviaPartido) -> list[str]:
    from roleplay.servicios import entrevista

    sueltos = {campo: getattr(previa, campo) for campo in
               ("posicion", "posicion_rival", "racha_club", "racha_rival", "cruce", "goleador", "goles_goleador")}
    datos = {"nombre": perfil.nombre_jugador, "apellido": entrevista.apellido(perfil), "club": previa.club,
             "rival": previa.rival, **{k: v for k, v in sueltos.items() if v}}
    cruces = cruce.cruces(perfil.id, previa.rival, None, entrevista._carrera())
    carrera = entrevista._carrera()
    candidatos, pesos = entrevista.temas_comunes(perfil, datos, cruces, entrevista.contexto_de_club(perfil, carrera),
                                                 previa=True, carrera=carrera)
    candidatos["tactica"] += [(1, "pv_tac_generico", datos)]
    simbolo, diferencia = como_llegan(previa)
    if simbolo:  # la pregunta de la tabla sale de la diferencia REAL (no "tan cerca" contra el ultimo)
        candidatos["tactica"].append((5, simbolo, {**datos, "diferencia": diferencia}))
    candidatos["racha"] += [(4, "pv_tac_racha", datos), (6, "pv_tac_cruce", datos), (5, "pv_tac_goleador", datos)]
    candidatos["vestuario"].append((1, "pv_ves_generico", datos))
    for c in cruces:
        if c.tipo in ("meta_cerca", "ex_club_traidor", "ex_club_idolo"):
            tema = "racha" if c.tipo == "meta_cerca" else "hinchada"
            candidatos[tema].append((c.peso, f"pv_ves_{c.tipo}", {**datos, **c.datos}))
    pesos["tactica"] += 1  # en la previa, el rival y la tabla mandan
    pesos["racha"] += 1
    return entrevista.armar_conferencia(perfil, candidatos, pesos, _contexto(previa), cruces)


CERCA_PUESTOS, CERCA_PUNTOS = 3, 6


def como_llegan(previa: PreviaPartido) -> tuple[str, int]:
    """El simbolo de la pregunta de la tabla y la diferencia de puntos: parejos, favoritos o de abajo."""
    if not previa.puesto or not previa.puesto_rival:
        return "", 0
    diferencia = abs(previa.puntos - previa.puntos_rival)
    if abs(previa.puesto - previa.puesto_rival) <= CERCA_PUESTOS or diferencia <= CERCA_PUNTOS:
        return "pv_tac_tabla", diferencia
    return ("pv_tac_tabla_favorito" if previa.puesto < previa.puesto_rival else "pv_tac_tabla_abajo"), diferencia


def _contexto(previa: PreviaPartido) -> str:
    return (f"Conferencia PREVIA (todavia no se jugo): {previa.club} {previa.resumen}.\n"
            + "\n".join(f"- {d}" for d in previa.datos))


def evaluar_previa(
    perfil: PlayerProfile, previa: PreviaPartido, respuestas: list[tuple[str, str]]
) -> ReaccionPrevia:
    from roleplay.servicios import entrevista

    lectura = lexico.leer([r for _, r in respuestas])
    delta = BASE_PREVIA[lectura.eje] * (1 + min(lectura.intensidad, 9) / 6)
    if lectura.eje in entrevista.PERSONALIDAD_CALZA.get(perfil.personalidad, set()):
        delta += 1
    if lectura.palabras < entrevista.PALABRAS_SECAS and perfil.personalidad != "reservado":
        delta -= 1
    if lectura.promesa:
        delta += 1
    delta = max(-DELTA_REPUTACION_MAXIMO, min(DELTA_REPUTACION_MAXIMO, round(delta)))
    datos = {"rival": previa.rival, "club": previa.club, "apellido": entrevista.apellido(perfil)}
    cruces = cruce.cruces(perfil.id, previa.rival, None, entrevista._carrera())
    cita = lectura.cita if lectura.palabras >= entrevista.PALABRAS_SECAS else ""
    with narrador(perfil.id, "entrevista") as escritor:
        titular = escritor.decir("pv_titular_cita" if cita else "pv_titular", **datos, cita=cita)
        texto = entrevista.reaccionar(escritor, perfil, lectura, delta, "r_apertura_previa", datos, cruces)
        nuevo_gancho = entrevista.gancho(escritor, lectura)
    carino = CARINO_PREVIA.get(lectura.eje, 0)
    hibrida = entrevista.reaccion_con_ia(perfil, _contexto(previa), respuestas, cruces, lectura, delta, carino,
                                         DELTA_REPUTACION_MAXIMO, con_titular=True)
    if hibrida:
        texto, delta, carino, cita = hibrida["reaccion"], hibrida["delta"], hibrida["carino"], hibrida["cita"]
        titular = hibrida["titular"] or titular
        nuevo_gancho = hibrida["gancho"] or nuevo_gancho
    return ReaccionPrevia(
        titular=titular, reaccion_prensa=texto, tono=entrevista.tono_de(delta), delta_reputacion=delta,
        nuevo_gancho_narrativo=nuevo_gancho, eje=lectura.eje, cita=cita, delta_carino=carino,
    )


def noticia_de_previa(perfil: PlayerProfile, previa: PreviaPartido, reaccion: ReaccionPrevia) -> NoticiaPrensa:
    """La conferencia queda en la central de noticias."""
    return NoticiaPrensa(
        player_id=perfil.id,
        categoria="jugador",
        tono=reaccion.tono,
        titular=reaccion.titular,
        cuerpo=reaccion.reaccion_prensa,
        hitos=[f"previa:{previa.clave}"],
    )
