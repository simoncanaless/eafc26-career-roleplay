"""
Persistencia en SQLite (`career_roleplay.db`, en la raiz del proyecto).

Cada dataclass de models.py vive en una tabla (TABLAS) y los campos se
guardan en columnas con el mismo nombre: listas y dicts como JSON, bools
como 0/1. Asi, agregar un campo a un modelo es agregarlo al CREATE TABLE
y a COLUMNAS_AGREGADAS (la DB del usuario ya existe y tiene datos), sin
tocar ninguna funcion de lectura o escritura.

El estado que evoluciona (reputacion, prensa, seguidores...) vive en
`player_profile.estado_json`, para no migrar el esquema por cada modulo.
"""

import json
import sqlite3
from contextlib import contextmanager
from dataclasses import fields
from datetime import datetime
from typing import Iterator, Optional, TypeVar

from roleplay import config
from roleplay.models import InstagramPost, MatchInterviewRecord, NoticiaPrensa, PlayerProfile

SCHEMA = """
CREATE TABLE IF NOT EXISTS player_profile (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre_jugador TEXT NOT NULL,
    pais_padres TEXT,
    ciudad_natal TEXT,
    fecha_nacimiento TEXT,
    contexto_socioeconomico TEXT,
    personalidad TEXT,
    motivacion TEXT,
    estado_relacion TEXT,
    nombre_pareja TEXT,
    anecdota_personal TEXT,
    backstory_generado TEXT,
    ganchos_narrativos TEXT,   -- JSON list
    reputacion_inicial INTEGER,
    fecha_creacion TEXT,
    club_actual TEXT DEFAULT '',
    estado_json TEXT           -- JSON libre para los modulos
);

CREATE TABLE IF NOT EXISTS partido_entrevista (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    player_id INTEGER NOT NULL,
    fecha TEXT,
    goles_equipo INTEGER,
    goles_rival INTEGER,
    equipo_rival TEXT,
    goles_jugador INTEGER,
    asistencias_jugador INTEGER,
    rating_jugador REAL,
    minutos_jugados INTEGER,
    tarjeta_amarilla INTEGER,
    tarjeta_roja INTEGER,
    hombre_del_partido INTEGER,
    preguntas_entrevista TEXT,   -- JSON list
    respuestas_jugador TEXT,     -- JSON list, paralela a preguntas_entrevista
    reaccion_prensa TEXT,
    delta_reputacion INTEGER,
    origen TEXT DEFAULT '',
    fecha_juego TEXT DEFAULT '',
    FOREIGN KEY(player_id) REFERENCES player_profile(id)
);

-- Nombres que la partida de FC 26 no trae (jugadores, copas), reconocidos
-- una vez por la IA y guardados para siempre. nombre '' = no lo reconocio.
CREATE TABLE IF NOT EXISTS nombre_conocido (
    tipo TEXT NOT NULL,      -- 'jugador' | 'competicion'
    id INTEGER NOT NULL,     -- id de EA
    nombre TEXT,
    seguro INTEGER,
    PRIMARY KEY (tipo, id)
);

CREATE TABLE IF NOT EXISTS noticia_prensa (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    player_id INTEGER NOT NULL,
    fecha TEXT,
    categoria TEXT,
    tono TEXT,
    titular TEXT,
    cuerpo TEXT,
    hitos TEXT,  -- JSON list
    FOREIGN KEY(player_id) REFERENCES player_profile(id)
);

CREATE TABLE IF NOT EXISTS instagram_post (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    player_id INTEGER NOT NULL,
    fecha TEXT,
    texto TEXT,
    likes INTEGER,
    crecimiento_seguidores INTEGER,
    comentarios TEXT,  -- JSON list de {"autor","texto","tono"}
    FOREIGN KEY(player_id) REFERENCES player_profile(id)
);
"""

# Columnas que se agregaron despues de que la DB del usuario ya existia:
# (tabla, columna, definicion). init_db las crea si faltan.
COLUMNAS_AGREGADAS = [
    ("player_profile", "club_actual", "TEXT DEFAULT ''"),
    ("partido_entrevista", "origen", "TEXT DEFAULT ''"),
    ("partido_entrevista", "fecha_juego", "TEXT DEFAULT ''"),
]

TABLAS = {
    PlayerProfile: "player_profile",
    MatchInterviewRecord: "partido_entrevista",
    NoticiaPrensa: "noticia_prensa",
    InstagramPost: "instagram_post",
}

REPUTACION_POR_DEFECTO = 50

Modelo = TypeVar("Modelo", PlayerProfile, MatchInterviewRecord, NoticiaPrensa, InstagramPost)


@contextmanager
def conectar() -> Iterator[sqlite3.Connection]:
    """Conexion con commit al salir bien, rollback si hay una excepcion,
    y siempre cerrada (el `with conn` de sqlite3 no la cierra)."""
    conn = sqlite3.connect(config.DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        with conn:
            yield conn
    finally:
        conn.close()


def init_db() -> None:
    with conectar() as conn:
        conn.executescript(SCHEMA)
        for tabla, columna, definicion in COLUMNAS_AGREGADAS:
            existentes = {fila["name"] for fila in conn.execute(f"PRAGMA table_info({tabla})")}
            if columna not in existentes:
                conn.execute(f"ALTER TABLE {tabla} ADD COLUMN {columna} {definicion}")


# ---- Mapeo generico dataclass <-> fila ----


def _a_columna(valor):
    if isinstance(valor, (list, dict)):
        return json.dumps(valor, ensure_ascii=False)
    if isinstance(valor, bool):
        return int(valor)
    return valor


def _desde_fila(clase: type[Modelo], fila: sqlite3.Row) -> Modelo:
    """Arma la dataclass desde la fila. Lo que venga NULL (o falte, en una
    DB vieja) toma el valor por defecto del modelo."""
    por_defecto = clase()
    columnas = set(fila.keys())
    datos = {}
    for campo in fields(clase):
        valor = fila[campo.name] if campo.name in columnas else None
        defecto = getattr(por_defecto, campo.name)
        if valor is None:
            valor = defecto
        elif isinstance(defecto, (list, dict)):
            valor = json.loads(valor) if valor else defecto
        elif isinstance(defecto, bool):
            valor = bool(valor)
        datos[campo.name] = valor
    return clase(**datos)


def _insertar(objeto) -> int:
    tabla = TABLAS[type(objeto)]
    columnas = [campo.name for campo in fields(objeto) if campo.name != "id"]
    with conectar() as conn:
        cursor = conn.execute(
            f"INSERT INTO {tabla} ({', '.join(columnas)}) "
            f"VALUES ({', '.join('?' * len(columnas))})",
            [_a_columna(getattr(objeto, columna)) for columna in columnas],
        )
        return cursor.lastrowid


def _cargar_de_jugador(clase: type[Modelo], player_id: int, limite: int = -1) -> list[Modelo]:
    """Registros del jugador, del mas reciente al mas viejo. limite=-1: todos."""
    with conectar() as conn:
        filas = conn.execute(
            f"SELECT * FROM {TABLAS[clase]} WHERE player_id = ? ORDER BY id DESC LIMIT ?",
            (player_id, limite),
        ).fetchall()
    return [_desde_fila(clase, fila) for fila in filas]


# ---- Perfiles ----


def save_profile(profile: PlayerProfile) -> int:
    return _insertar(profile)


def load_profile(profile_id: int) -> Optional[PlayerProfile]:
    with conectar() as conn:
        fila = conn.execute("SELECT * FROM player_profile WHERE id = ?", (profile_id,)).fetchone()
    return _desde_fila(PlayerProfile, fila) if fila is not None else None


def load_latest_profile() -> Optional[PlayerProfile]:
    with conectar() as conn:
        fila = conn.execute("SELECT * FROM player_profile ORDER BY id DESC LIMIT 1").fetchone()
    return _desde_fila(PlayerProfile, fila) if fila is not None else None


def agregar_gancho_narrativo(player_id: int, gancho: str) -> None:
    """Suma un gancho narrativo nuevo (ej. uno que salio de una respuesta
    en una entrevista), sin repetir los que ya estan."""
    gancho = gancho.strip()
    if not gancho:
        return
    with conectar() as conn:
        fila = conn.execute(
            "SELECT ganchos_narrativos FROM player_profile WHERE id = ?", (player_id,)
        ).fetchone()
        if fila is None:
            return
        ganchos = json.loads(fila["ganchos_narrativos"] or "[]")
        if gancho not in ganchos:
            ganchos.append(gancho)
            conn.execute(
                "UPDATE player_profile SET ganchos_narrativos = ? WHERE id = ?",
                (json.dumps(ganchos, ensure_ascii=False), player_id),
            )


def actualizar_club(player_id: int, club: str) -> None:
    """El club cambia con las transferencias; el resto del quiz queda fijo."""
    with conectar() as conn:
        conn.execute(
            "UPDATE player_profile SET club_actual = ? WHERE id = ?", (club.strip(), player_id)
        )


# ---- estado_json: reputacion, prensa, seguidores ----


def _decodificar_estado(fila: sqlite3.Row) -> tuple[dict, int]:
    reputacion_inicial = fila["reputacion_inicial"]
    if reputacion_inicial is None:
        reputacion_inicial = REPUTACION_POR_DEFECTO
    return json.loads(fila["estado_json"] or "{}"), reputacion_inicial


def _leer_estado(player_id: int) -> Optional[tuple[dict, int]]:
    """(estado_json, reputacion_inicial) del jugador, o None si no existe."""
    with conectar() as conn:
        fila = conn.execute(
            "SELECT reputacion_inicial, estado_json FROM player_profile WHERE id = ?", (player_id,)
        ).fetchone()
    return _decodificar_estado(fila) if fila is not None else None


@contextmanager
def _editar_estado(player_id: int) -> Iterator[tuple[dict, int]]:
    """Abre el estado_json para modificarlo en el lugar y lo guarda al
    salir, todo en la misma transaccion (leer y escribir no se cruzan)."""
    with conectar() as conn:
        fila = conn.execute(
            "SELECT reputacion_inicial, estado_json FROM player_profile WHERE id = ?", (player_id,)
        ).fetchone()
        if fila is None:
            raise ValueError(f"No existe ningun perfil con id {player_id}")
        estado, reputacion_inicial = _decodificar_estado(fila)
        yield estado, reputacion_inicial
        conn.execute(
            "UPDATE player_profile SET estado_json = ? WHERE id = ?",
            (json.dumps(estado, ensure_ascii=False), player_id),
        )


def _reputacion(estado: dict, reputacion_inicial: int) -> int:
    return estado.get("reputacion_actual", reputacion_inicial)


def _seguidores(estado: dict, reputacion_inicial: int) -> int:
    # Quien nunca publico arranca con una base ligada a su reputacion: un
    # desconocido no parte en 0, pero tampoco con millones.
    return estado.get("seguidores_instagram", max(100, reputacion_inicial * 5))


def get_reputacion_actual(player_id: int) -> int:
    """Reputacion que evoluciona con el tiempo. Si nunca cambio, es la
    reputacion_inicial calculada al crear el personaje."""
    leido = _leer_estado(player_id)
    return _reputacion(*leido) if leido else REPUTACION_POR_DEFECTO


def aplicar_delta_reputacion(player_id: int, delta: int, motivo: str) -> int:
    """Suma `delta` a la reputacion (acotada a 0-100), deja el cambio en
    estado_json.historial_reputacion y devuelve la reputacion resultante."""
    with _editar_estado(player_id) as (estado, reputacion_inicial):
        nueva = max(0, min(100, _reputacion(estado, reputacion_inicial) + delta))
        estado["reputacion_actual"] = nueva
        estado.setdefault("historial_reputacion", []).append(
            {
                "delta": delta,
                "motivo": motivo,
                "reputacion_resultante": nueva,
                "fecha": datetime.now().isoformat(),
            }
        )
    return nueva


def get_estado_prensa(player_id: int) -> dict:
    """Que checkpoints de prensa ya se reportaron (estado_json.prensa)."""
    leido = _leer_estado(player_id)
    return leido[0].get("prensa", {}) if leido else {}


def set_estado_prensa(player_id: int, estado_prensa: dict) -> None:
    with _editar_estado(player_id) as (estado, _):
        estado["prensa"] = estado_prensa


def get_seguidores(player_id: int) -> int:
    leido = _leer_estado(player_id)
    return _seguidores(*leido) if leido else 0


def sumar_seguidores(player_id: int, delta: int) -> int:
    """Suma (o resta) seguidores sin bajar de 0 y devuelve el total."""
    with _editar_estado(player_id) as (estado, reputacion_inicial):
        total = max(0, _seguidores(estado, reputacion_inicial) + delta)
        estado["seguidores_instagram"] = total
    return total


# ---- Partidos, noticias y posts ----


def save_match_interview(record: MatchInterviewRecord) -> int:
    return _insertar(record)


def load_match_interviews(player_id: int) -> list[MatchInterviewRecord]:
    """Del partido mas reciente al mas viejo (servicios/prensa.py cuenta con eso)."""
    return _cargar_de_jugador(MatchInterviewRecord, player_id)


def save_noticia_prensa(noticia: NoticiaPrensa) -> int:
    return _insertar(noticia)


def load_noticias_prensa(player_id: int, limite: int = 50) -> list[NoticiaPrensa]:
    return _cargar_de_jugador(NoticiaPrensa, player_id, limite)


def save_instagram_post(post: InstagramPost) -> int:
    return _insertar(post)


def load_instagram_posts(player_id: int, limite: int = 50) -> list[InstagramPost]:
    return _cargar_de_jugador(InstagramPost, player_id, limite)


# ---- nombres reconocidos (jugadores y copas de la partida de FC 26) ----


def get_nombres_conocidos(tipo: str, ids) -> dict[int, tuple[str, bool]]:
    """{id: (nombre, seguro)} de los que ya se preguntaron (incluye los que
    la IA no reconocio, con nombre '', para no volver a preguntar)."""
    ids = list(ids)
    if not ids:
        return {}
    with conectar() as conn:
        filas = conn.execute(
            f"SELECT id, nombre, seguro FROM nombre_conocido WHERE tipo = ? AND id IN ({','.join('?' * len(ids))})",
            (tipo, *ids),
        ).fetchall()
    return {fila["id"]: (fila["nombre"] or "", bool(fila["seguro"])) for fila in filas}


def guardar_nombres_conocidos(tipo: str, nombres: dict) -> None:
    """nombres: {id: (nombre, seguro)}"""
    with conectar() as conn:
        conn.executemany(
            "INSERT OR REPLACE INTO nombre_conocido (tipo, id, nombre, seguro) VALUES (?, ?, ?, ?)",
            [(tipo, ident, nombre, int(seguro)) for ident, (nombre, seguro) in nombres.items()],
        )


def get_estado_partida(player_id: int) -> dict:
    """Lo que se leyo de la partida de FC 26 la ultima vez (totales del
    jugador por competicion, ultimo partido cargado): estado_json.partida."""
    leido = _leer_estado(player_id)
    return leido[0].get("partida", {}) if leido else {}


def set_estado_partida(player_id: int, estado_partida: dict) -> None:
    with _editar_estado(player_id) as (estado, _):
        estado["partida"] = estado_partida
