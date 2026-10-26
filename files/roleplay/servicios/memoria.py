"""
La memoria del roleplay para la IA (pedido de Simon, 2026-10-20: "que las
cosas se sientan vivas, como roleplay, no como un guion").

`cronica(player_id)` junta en un texto corto lo que esta vivo en la historia
del jugador: quien es, como viene, lo que dijo en las ultimas conferencias, lo
que le paso (titulares, vida, pareja, hinchada, contrato) y las tramas que
quedaron abiertas. Cada pedido a la IA lo lleva (`ia.pedir_json(...,
memoria=...)`), asi los periodistas, los hinchas y los demas se acuerdan y
contestan a la historia en vez de a un hecho suelto.

Solo LEE la base. Los hechos y los numeros siguen saliendo del codigo: esto es
contexto, y la IA tiene prohibido sacar de aca datos nuevos (ver ia.REGLAS y
la guardia de hechos). `anotar_dichos()` guarda lo que respondio en cada
conferencia (post y previa), que si no se perdia.
"""

from typing import Optional

from roleplay import database

MAXIMO = 2400  # caracteres: que entre holgado en cada pedido (Groq gratis cuenta tokens por minuto)


def _corto(texto: str, maximo: int) -> str:
    texto = " ".join(str(texto or "").split())
    return texto if len(texto) <= maximo else texto[: maximo - 1].rsplit(" ", 1)[0] + "…"


def anotar_dichos(player_id: Optional[int], tipo: str, rival: str, respuestas: list[str], cita: str = "",
                  fecha: str = "") -> None:
    """Lo que respondio en una conferencia ("post" o "previa"). Nunca falla."""
    if not player_id:
        return
    try:
        database.agregar_dicho(player_id, {
            "tipo": tipo, "rival": rival, "fecha": fecha, "cita": _corto(cita, 200),
            "respuestas": [_corto(r, 260) for r in respuestas if str(r or "").strip()][:3],
        })
    except Exception:  # noqa: BLE001 (la memoria nunca frena una conferencia)
        pass


def _personaje(perfil) -> list[str]:
    lineas = [f"{perfil.nombre_jugador}: personalidad {perfil.personalidad}, lo mueve {perfil.motivacion.replace('_', ' ')}"
              + (f", de {perfil.ciudad_natal}" if perfil.ciudad_natal else "") + "."]
    if perfil.backstory_generado:
        lineas.append("Su historia: " + _corto(perfil.backstory_generado, 320))
    return lineas


def _momento(perfil, estado: dict) -> list[str]:
    lineas = []
    reputacion = estado.get("reputacion_actual", perfil.reputacion_inicial)
    cambios = [h for h in estado.get("historial_reputacion", [])[-3:] if h.get("motivo")]
    lineas.append(f"Reputacion {reputacion}/100" + (
        " (ultimos cambios: " + "; ".join(f"{h['delta']:+d} {_corto(h['motivo'], 60)}" for h in cambios) + ")"
        if cambios else "") + ".")
    partidos = [r for r in database.load_match_interviews(perfil.id) if r.origen != "previa"][:3]
    if partidos:
        lineas.append("Ultimos partidos (el mas reciente primero): " + "; ".join(
            f"{r.goles_equipo}-{r.goles_rival} vs {r.equipo_rival or 'rival'} ({r.goles_jugador} goles suyos, "
            f"nota {r.rating_jugador:.1f})" for r in partidos) + ".")
    return lineas


def _dichos(estado: dict) -> list[str]:
    lineas = []
    for d in estado.get("conferencias", {}).get("dichos", [])[:3]:
        cuando = "antes de jugar con" if d.get("tipo") == "previa" else "despues de jugar con"
        dicho = " / ".join(f"«{r}»" for r in d.get("respuestas", []))
        if dicho:
            lineas.append(f"- {cuando} {d.get('rival') or 'el rival'}: {dicho}")
    return (["Lo que dijo en sus ultimas conferencias (textual):"] + lineas) if lineas else []


def _vida(perfil, estado: dict) -> list[str]:
    lineas = []
    amor = estado.get("amor") or {}
    pareja = (amor.get("pareja") or {}).get("nombre")
    if pareja and amor.get("estado") not in (None, "soltero"):
        lineas.append(f"Pareja: {pareja} ({amor.get('estado')}"
                      + (", romance secreto" if amor.get("secreto") else "") + ").")
    elif amor.get("estado") == "soltero":
        lineas.append("Esta soltero.")
    hijos = amor.get("hijos") or []
    if hijos:
        lineas.append("Hijos: " + ", ".join(h.get("nombre", "?") for h in hijos) + ".")
    momentos = [h for h in amor.get("historial", [])[-2:] if h.get("titulo")]
    if momentos:
        lineas.append("Con su pareja, hace poco: " + "; ".join(_corto(h["titulo"], 80) for h in momentos) + ".")
    clubes = estado.get("clubes") or {}
    actual = (clubes.get("clubes") or {}).get(str(clubes.get("actual")))
    if actual:
        carino = actual.get("carino", 50)
        animo = "lo idolatra" if carino >= 80 else "lo quiere" if carino >= 60 else "esta en contra" if carino < 30 else "tibia"
        lineas.append(f"La hinchada de {actual.get('nombre')}: {animo} (carino {carino}/100).")
    eventos = [e for e in (estado.get("eventos") or {}).get("historial", [])[-3:] if e.get("titulo")]
    if eventos:
        lineas.append("Le paso hace poco: " + "; ".join(_corto(e["titulo"], 80) for e in eventos) + ".")
    economia = estado.get("economia") or {}
    from roleplay.servicios import autos as autos_

    garage = []
    for p in economia.get("posesiones", []):
        if p.get("articulo", "").startswith("auto:") and p["articulo"][5:] in autos_.POR_ID:
            config = autos_.Configuracion.desde_dict(p.get("config") or {"modelo": p["articulo"][5:]})
            garage.append(f"{autos_.POR_ID[config.modelo].nombre_completo} {autos_.describir(config)}".strip())
    if garage:
        lineas.append("Su garage: " + "; ".join(_corto(g, 110) for g in garage[-3:]) + ".")
    from roleplay.servicios import ofertas as ofertas_de_clubes, patrocinios

    marcas = [patrocinios.nombre_de(c) for c in (economia.get("patrocinios") or {}).get("contratos", [])]
    if any(marcas):
        lineas.append("Marcas que lo patrocinan: " + ", ".join(m for m in marcas[:6] if m) + ".")
    ofertas = [o.get("club") for o in ofertas_de_clubes.abiertas(economia) if o.get("club")]
    if ofertas:
        lineas.append("Ofertas de otros clubes sobre la mesa: " + ", ".join(ofertas) + ".")
    return lineas


def _tramas(perfil) -> list[str]:
    ganchos = [g for g in perfil.ganchos_narrativos if g][-3:]
    return ["Tramas que quedaron abiertas en conferencias anteriores: " + " | ".join(_corto(g, 140) for g in ganchos)] if ganchos else []


def _titulares(perfil) -> list[str]:
    noticias = database.load_noticias_prensa(perfil.id, limite=6)
    if not noticias:
        return []
    return ["Ultimos titulares (el mas reciente primero):"] + [f"- {_corto(n.titular, 140)}" for n in noticias]


def cronica(player_id: Optional[int], maximo: int = MAXIMO) -> str:
    """La historia viva del jugador en texto corto ("" sin perfil). Nunca falla."""
    if not player_id:
        return ""
    try:
        perfil = database.load_profile(player_id)
        if perfil is None:
            return ""
        estado = perfil.estado_json or {}
        partes = []
        for seccion in (_personaje(perfil), _momento(perfil, estado), _dichos(estado), _vida(perfil, estado),
                        _tramas(perfil), _titulares(perfil)):
            partes.extend(seccion)
        texto = "\n".join(partes)
        return texto if len(texto) <= maximo else texto[:maximo].rsplit("\n", 1)[0]
    except Exception:  # noqa: BLE001 (sin memoria la IA escribe igual)
        return ""
