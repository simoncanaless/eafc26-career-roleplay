"""Como se le presenta el jugador a la IA. Lo comparten los prompts de
entrevistas, prensa e Instagram: un dato nuevo del personaje (ej. la
reputacion por club, cuando exista) se agrega aca una vez y lo ven todos."""

from roleplay.models import PERSONALIDADES, PlayerProfile


def ficha_jugador(perfil: PlayerProfile, *, backstory: bool = False, ganchos: bool = False) -> str:
    lineas = [
        f"Jugador: {perfil.nombre_jugador}",
        f"Club actual: {perfil.club_actual or '(no definido)'}",
        f"Personalidad publica: {PERSONALIDADES.get(perfil.personalidad, '')}",
    ]
    if backstory:
        lineas.append(f"Backstory: {perfil.backstory_generado or '(sin backstory)'}")
    if ganchos:
        lineas.append("Ganchos narrativos / rumores activos sobre su vida:")
        lineas.extend(f"- {gancho}" for gancho in perfil.ganchos_narrativos)
        if not perfil.ganchos_narrativos:
            lineas.append("(ninguno)")
    return "\n".join(lineas)
