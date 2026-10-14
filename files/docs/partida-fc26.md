# Leer la partida de carrera de FC 26 (investigacion e implementacion, 2026-10-14)

**Implementado** en `roleplay/partida/` (lector) y `roleplay/servicios/partida_real.py`
(lo que la app hace con eso). Probado con la partida real de Simon y con un guardado falso
del mismo formato (`tests/fabrica_partida.py`).

Objetivo: que las entrevistas y la prensa usen lo que paso de verdad en la
carrera (resultados, tablas, goles, traspasos) sin capturas de pantalla.

**Conclusion: se puede, leyendo el archivo de guardado.** No se toca el juego
(ni su memoria ni sus archivos: se lee una COPIA del guardado), asi que funciona
con el anticheat activo y no afecta el juego online. Probado sobre una copia de
la partida real de Simon: todo lo de abajo salio de ahi.

## Donde esta

`%LOCALAPPDATA%\EA SPORTS FC 26\settings\`

| Archivo | Que es |
|---|---|
| `CmPlr<fecha>` | Carrera **jugador** (la de Simon: `CmPlr20260811003112961`, "Carrera - Prog. de Futbolista 2") |
| `CmMgrC…` / `CmMgrL…` | Carrera entrenador |
| `Squads…`, `FutSquads…`, `Settings…` | Plantillas, FUT, ajustes |

Todos los guardados de carrera pesan lo mismo (15.274.941 bytes, relleno de
ceros al final). **No estan encriptados ni comprimidos.** El juego los
reescribe al guardar (autoguardado tras los partidos): la app debe leer el
`CmPlr*` mas reciente y trabajar sobre una copia.

## Estructura

- Cabecera `FBCHUNKS`; en el offset 18, el nombre de la partida (termina en 0).
- **Dos bases de datos** en el formato DB de EA (firma `44 42 00 08 00 00 00 00`,
  little-endian): la de la carrera (33 tablas, ~1,3 MB) y la del mundo del
  juego (33 tablas, ~6,9 MB: 21.507 jugadores, 817 equipos, 48 ligas...).
  Formato: cabecera de 24 bytes + directorio de tablas (codigo de 4 letras +
  offset); cada tabla: cabecera de 36 bytes + descriptores de campo de 16
  bytes (tipo, bit de inicio, codigo, ancho en bits) + registros
  empaquetados en bits (LSB primero). Tipos: 0 texto, 3 entero, 4 float,
  13/14 texto comprimido. Referencia del formato:
  [api-eafc-files/docs/binary-format.md](https://github.com/ViniMacacari/api-eafc-files/blob/main/docs/binary-format.md)
  (ese repo NO tiene licencia: se uso solo como descripcion, el codigo es propio).
- **Secciones de carrera** marcadas `[largo][00 00 00][nombre en minusculas][01]`
  (90 en la partida de Simon: `teams`, `stndgs`, `stagadv`, `fixture`, `sched`,
  `compobj`, `stats`...).

Los campos de las bases vienen con codigos de 4 letras; sus nombres estan en
`fifa_ng_db-meta.xml`, un archivo de EA que NO usamos (no se puede repartir).
Los campos necesarios se identificaron por contenido.

## Lo que se pudo leer (verificado)

| Dato | Donde | Como |
|---|---|---|
| **Partidos** de todas las competiciones (2.514; 1.527 jugados) | dentro de la seccion `teams` | registros de 22 bytes: `FF 01`, indice u16, competicion u16, ronda u8, fecha u32 `AAAAMMDD`, hora u16 `HHMM`, local (u16 indice de tabla, u8 goles, u8 penales), visita (igual), jugado u8 |
| **Equipo de cada partido** | seccion `stagadv` | registros de 23 bytes `FF 01` + indice u16 + grupo u16 + id de equipo i32 + ... (indice de tabla -> equipo). Sus puntos estan en 0: la tabla en vivo se calcula con los partidos jugados |
| **Nombres de equipos** (100%) | base del mundo, tabla `lyxL` | nombre = campo `AUsv`; id = campo `mCXg` **+ 1** (se guarda restando 1: Real Madrid 242 -> 243, Man Utd 10 -> 11) |
| **Estadisticas por jugador y competicion** (18.308) | seccion `stndgs` (desde su inicio + 10) | registros de 73 bytes `01 01`; en bits: equipo 16/18 (-1), jugador 34/19 (-1), competicion 53/11, minutos 69/15, nota total 84/12 (decimas), goles 108/9, amarillas 117/7, rojas 124/6, partidos 130/8, asistencias 138/8, figura 146/8; y los ultimos 5 partidos (10 bytes c/u desde el byte 22: fecha 3/25, minutos 35/7, nota 42/7, goles 50/3) |

Ejemplos reales de la partida de Simon: Man Utd 7-0 Stoke City, Liverpool 2-5
Man Utd, Man Utd 4-2 Manchester City, Man Utd 6-2 SSC Napoli (competicion 122).
Su jugador es el **id 30999**: 34 partidos, 102 goles, 20 asistencias, 26 veces
figura, nota media 9,35. Bruno Fernandes = 212198 (los ids de jugador son los
mismos de siempre de EA / sofifa). Competiciones vistas: 808 (liga), 122
(europea), 617 (copa).

## Lo que se agrego al implementar

| Dato | Como |
|---|---|
| **Quien es el usuario** | base de carrera, tabla `mPrV` (nombre `HdeP`, apellido `rREd`); se busca el mismo nombre en `nQVU` (nombres editados: `HdeP`, apodo `xnfZ`, `rREd`, jugador `ykFq`). Simon = 30999 |
| **Su club** | el equipo de su actuacion mas reciente en un club (los clubes son los equipos que juegan partidos de liga) |
| **Quien jugo y marco en cada partido** | los ultimos 5 partidos de cada registro de estadisticas, con la misma fecha y competicion que el partido. En la partida de Simon, los goles de los jugadores suman el marcador en ~95% de los casos (el resto: autogoles) |
| **Ligas** | competicion con codigo `C<n>` -> tabla `onMQ` (id `aQrQ` + 1, nombre `HEQX`): C13 = Premier League. Competiciones en registros de 49 bytes `FF 01` (id, copia del id, nivel, padre, codigo) en la seccion `compavg`. Continental si subiendo por los padres se llega a una confederacion (nivel 1) antes que a un pais (nivel 2) |
| **Copas** | la partida no trae su nombre: la IA lo reconoce por sus equipos (Champions League, FA Cup, Carabao Cup) y queda guardado |
| **Ficha de un jugador** | tabla `CZUM` (id `ykFq`, nacimiento `WVIU` = dias desde 1582-10-14); tabla `RrqT` (vinculos: jugador `ykFq`, equipo `mCXg` + 1, posicion `vjla` 0-29: 25 = DC, 18 = MCO, 28 = suplente). Club + posicion + seleccion + nacimiento alcanzan para que la IA reconozca a los conocidos (Haaland, Isak, Gibbs-White, Grealish) |
| **Tabla de posiciones** | se calcula con los partidos jugados (la de `stagadv` viene en cero) |
| **Liga de cada equipo** (2026-10-14) | tabla `qdZF` del mundo (una fila por equipo, 817): liga `aQrQ` + 1, equipo `mCXg` + 1. Ligas especiales: 78 = selecciones de hombres ("Selecc. masc."), 2136 = selecciones de mujeres, 382 = "Agentes libres" (un equipo), 76 = Resto del mundo. Las ligas femeninas (WSL, Liga F...) tienen equipos propios |
| **Media, potencial, genero y posicion** (2026-10-14) | tabla `CZUM`: media `UERs`, potencial `mpuH` (en los 21.507 jugadores el potencial nunca es menor que la media; los de media mas alta son Haaland 92, Mbappe/Vinicius/Bellingham 91), genero `EveZ` (1 = jugadora: 2.149, todas las de selecciones femeninas), posicion preferida `wZQU` (mismos numeros que `vjla`: Haaland 25, Vinicius 27, Bellingham 18, De Bruyne 14). Simon (30999): media 79, potencial 94 |
| **Traspasos** (2026-10-14) | la partida no guarda un historial legible, pero `RrqT` dice el club de hoy: comparando dos lecturas de la MISMA partida salen los traspasos (`servicios/mercado.py`, foto en la tabla `club_visto` de la app). Verificado entre la partida 1 (feb-2025) y la 2 (ene-2027): 4.927 jugadores cambiaron de equipo, ej. un central del Bayern al Paris SG o un lateral derecho del Spurs al RB Leipzig |

## Pistas sin confirmar

- Base de carrera, tabla `NgwF`: parece el historial de clubes del jugador
  (Palermo -> Man Utd, con competiciones 808/617).
- Tabla `YMgA`: dos registros con montos 7.500.000 y 44.000.000 (¿traspasos?).
- Tabla `mPrV`: el jugador del usuario ("Simon", "Canales", "Riccardo
  Martinelli"), con 808 (su liga) y 145000 (¿sueldo?).
- Tablas `TtHG` (245) y `TPOP` (4.200): posibles traspasos del mundo.
- Seccion `compobj`: probablemente los nombres/codigos de las competiciones.

## Lo que NO esta en la partida

- **Nombres de los jugadores actuales**: la tabla de jugadores de la partida no
  trae a la mayoria (ej. 240243) y la de nombres es parcial. Los nombres viven en
  los archivos del juego. Opciones: una lista id -> nombre (los ids son los de
  sofifa), o aprenderlos de las capturas.

## Rendimiento

1,5 s leer todo (0,06 s las secciones con una expresion regular; 1,3 s las dos
bases completas, que se pueden limitar a las tablas que se usen).

## Riesgos

- Un parche del juego puede mover el formato: el lector tiene que validar cada
  registro (firmas, fechas, indices) y, si algo no calza, volver a la captura o
  a los datos a mano sin romperse.
- Leer siempre una copia y nunca escribir en el guardado.
