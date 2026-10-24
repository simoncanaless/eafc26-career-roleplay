"""Arma docs/consignas-ia.md con todas las consignas de la IA, tal cual estan en el codigo."""
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))
from roleplay.servicios import contratos, entrevista, feed, hinchada, ia, instagram, prensa  # noqa: E402

TAREAS = [
    ("Preguntas de la conferencia (post y previa)", "roleplay/servicios/entrevista.py", entrevista.SISTEMA_PREGUNTAS),
    ("Reaccion de la prensa a tus respuestas", "roleplay/servicios/entrevista.py", entrevista.SISTEMA_REACCION),
    ("Nota del diario sobre tu entrevista", "roleplay/servicios/prensa.py", prensa.SISTEMA_NOTA),
    ("Noticias de la prensa y de tu vida (reescritura)", "roleplay/servicios/prensa.py", prensa.SISTEMA_DIARIO),
    ("Comentarios de los hinchas (partidos y noticias)", "roleplay/servicios/hinchada.py", hinchada.SISTEMA_HINCHAS),
    ("Comentarios de tus posts de Instagram", "roleplay/servicios/instagram.py", instagram.SISTEMA_COMENTARIOS),
    ("Sugerir post (tu voz)", "roleplay/servicios/instagram.py", instagram.SISTEMA_POST),
    ("La directiva en la mesa del contrato", "roleplay/servicios/contratos.py", contratos.SISTEMA_DIRECTIVA),
    ("Feed global: el formato de cada pagina", "roleplay/servicios/feed.py",
     feed.SISTEMA_FEED + "\n\nFORMATOS POR CUENTA:\n" + "\n".join(f"- {k}: {v}" for k, v in feed.FORMATOS.items())
     + "\n\nFORMATOS POR TIPO:\n" + "\n".join(f"- {k}: {v}" for k, v in feed.FORMATO_POR_TIPO.items())),
]

partes = [
    "# Consignas de la IA",
    "",
    "Todo lo que se le manda a la IA (Groq, y Gemini de respaldo), tal cual esta en el codigo. "
    "Generado desde el codigo: si cambias una consigna, volve a generarlo.",
    "",
    "## Como se arma cada pedido",
    "",
    "Cada pedido tiene dos partes:",
    "",
    "**1. El mensaje de sistema** (las instrucciones), en este orden:",
    "1. La consigna de la tarea (abajo, una por tarea).",
    "2. Si el pedido lleva tu memoria: la consigna de VOZ.",
    "3. Las REGLAS DE ORO (en todos los pedidos).",
    "4. La forma exacta del JSON que tiene que devolver.",
    "",
    "**2. El mensaje del usuario** (los datos):",
    "1. `MEMORIA DEL ROLEPLAY (lo que ya paso)`: quien sos, como venis (reputacion, ultimos 3 partidos), lo que "
    "dijiste en tus ultimas conferencias (textual), tu vida (pareja, hinchada, eventos, marcas, ofertas), las tramas "
    "abiertas y los ultimos titulares (`servicios/memoria.py`, ~1.700 caracteres).",
    "2. `LO DE AHORA`: los datos de esa tarea (el partido, tus respuestas, las notas, el post...).",
    "",
    "## Lo que revisa el codigo despues (la IA no puede saltarselo)",
    "",
    "- **Numeros**: si un texto trae un numero que no estaba en los datos, se descarta (los ejemplos de las "
    "consignas no cuentan como datos: si copia un numero del ejemplo, tambien se descarta).",
    "- **Nombres propios**: si un texto nombra algo que no esta en los datos (\"Old Trafford\", \"Bombonera\"), se "
    "descarta. No cuentan las mayusculas de principio de oracion ni palabras comunes (Champions, Instagram, VAR...); "
    "los apodos de clubes conocidos (United, Red Devils, Citizens) valen.",
    "- **Hechos que no se inventan**: " + ", ".join(ia.HECHOS_QUE_NO_SE_INVENTAN) + ": si aparecen y no estan en "
    "los datos, se descarta.",
    "- **Nacionalidades**: un gentilicio (uruguayo, argentino...) que no corresponde con los datos, se descarta.",
    "- **Citas**: la cita de tu entrevista solo vale si son tus palabras textuales.",
    "- **Goleador rival**: si la reaccion de una previa trae al goleador del rival y vos no lo nombraste, se descarta.",
    "- **Deltas**: lo que suma o resta de reputacion y carino queda acotado (no puede pasarse del tope).",
    "- Lo descartado no se pierde: queda el texto del motor local.",
    "",
    "## REGLAS DE ORO (en todos los pedidos)",
    "",
    "```",
    ia.REGLAS,
    "```",
    "",
    "## VOZ (cuando el pedido lleva tu memoria)",
    "",
    "```",
    ia.VOZ,
    "```",
    "",
    "## Las consignas de cada tarea",
]
for titulo, archivo, texto in TAREAS:
    partes += ["", f"### {titulo}", "", f"`{archivo}`", "", "```", texto, "```"]

destino = RAIZ / "docs" / "consignas-ia.md"
destino.write_text("\n".join(partes) + "\n", encoding="utf-8")
print(destino, len("\n".join(partes)))
