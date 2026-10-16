# EAFC 26 Career Roleplay

App de escritorio (Python + PySide6) que agrega una capa de roleplay narrativo al
Modo Carrera Jugador de EAFC 26 **sin modificar el juego** (corre al lado, como
Discord/OBS: lee la partida guardada, nunca escribe archivos ni toca la memoria del juego): creacion de personaje con backstory, entrevistas
post-partido (escritas o por voz), prensa espontanea, Instagram ficticio y reputacion
que evoluciona. Proyecto personal de Simon (estudiante de Ing. Informatica, Chile).

**Motor local + IA hibrida OPCIONAL (desde el 2026-10-16, pedido de Simon)**: todos los
textos los arma primero el motor narrativo local (`servicios/narrador.py` + `roleplay/datos/`),
offline y al instante; si hay clave de Groq/Gemini, `servicios/ia.py` REESCRIBE encima
(preguntas, reaccion de la prensa, nota de la entrevista, comentarios de Instagram y de la
hinchada) para contestar a lo que escribio el jugador. Los hechos (resultados, goles, tablas,
cruces) y los numeros base los sigue calculando el codigo y se le pasan a la IA; sus deltas
quedan acotados y una cita solo vale si es textual. Sin clave, con "solo motor local" o sin
internet, la app funciona igual que antes. (Del 2026-10-15 al 16 la app fue 100% sin IA:
`roleplay/gemini.py`, `servicios/contexto.py`, `DialogoClave` y la captura con IA no volvieron.)
Corre en Windows, desde `C:\Users\canal\Desktop\Proyecto Fifa\files`, con un venv en
`.venv` (Python 3.11.9). Repo git en `Proyecto Fifa\` (rama `main`; identidad
configurada solo en este repo).

## Para retomar en una sesion nueva (leer primero)

- **Empezar cada mensaje con "Simón"**. Respuestas en espanol, directas y practicas.
- Abrir la sesion en `C:\Users\canal\Desktop\Proyecto Fifa` (no en Proyecto Fitogreen: carga otro CLAUDE.md enorme).
- **Repo**: https://github.com/simoncanaless/eafc26-career-roleplay (PUBLICO, rama `main`; `gh` autenticado como
  `simoncanaless`, ejecutable en `C:\Program Files\GitHub CLI\gh.exe`). Despues de cada cambio con las pruebas en
  verde: commit y push (`files\scripts\sincronizar_git.py "mensaje"` revisa que no se cuele nada privado). Al ser
  publico: nunca subir claves, la base, fotos ni datos personales.
- **Uso**: Simon tiene plan Pro y pide **parar al 90% del uso semanal** (mirarlo con la herramienta de uso antes de
  tareas largas y avisarle). Trabajar con pocas llamadas.
- **Estado al 2026-10-16** (328 pruebas en verde, todo en GitHub):
  1. Noticias inventadas: SACADAS el 2026-10-16 (la prensa solo escribe sobre lo real).
  2. Pilar 3 (tienda universal): a medias, falta la pantalla (detalle en Estado / roadmap).
  3. Pilar 4 (overlay bimodal): HECHO el 2026-10-16, falta probarlo encima del juego real.
  4. IA hibrida (Groq -> Gemini -> motor local): HECHA el 2026-10-16; falta probarla con una
     clave real (Simon la pega en Ajustes > Motor narrativo e IA hibrida > Probar IA).
- Arreglado el 2026-10-15: la base real de Simon no tenia `respuestas_jugador`/`reaccion_prensa`/`delta_reputacion`
  en `partido_entrevista` (nunca se habia guardado una entrevista); `database.init_db` ahora agrega sola cualquier
  columna que falte. Hay que cerrar y abrir la app para que lo tome.
- `files/CODIGO_TEXTO.txt` (sin trackear) no lo creo Claude: preguntar antes de subirlo o borrarlo.

## Como correrlo

```powershell
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe app.py                  # menu unificado
.venv\Scripts\python.exe app.py entrevistas      # o: personaje | instagram (modulo suelto)
.venv\Scripts\python.exe -m unittest discover -s tests
.venv\Scripts\python.exe scripts\seed_test_matches.py [--borrar]   # 5 partidos de prueba
.venv\Scripts\python.exe scripts\crear_acceso_directo.py [--sin-escritorio]
.venv\Scripts\python.exe app.py --jugar          # abre EA FC 26 (Steam) + la app en la sala de prensa
.venv\Scripts\python.exe app.py --diagnostico    # revisa todo y sale (diagnostico.txt)
.venv\Scripts\python.exe scripts\empaquetar.py   # paquete para amigos (requirements-dev.txt)
```

**Iconos del escritorio** (`servicios/accesos.py`, tambien desde Ajustes en la app):
"EA FC 26.url" (`steam://rungameid/3405690`, el juego normal) y "EA FC 26 + Roleplay.lnk"
(la app con `--jugar`: abre el MISMO juego por su plataforma y la app). El FC 26 de Simon
esta en Steam, biblioteca `F:\SteamLibrary` (EA app instalada, la usa Steam).

**Paquete para amigos**: `dist\EAFC Roleplay (amigos).zip` (~195 MB, casi todo Chromium) con
`EAFC Roleplay.exe` (PyInstaller onedir, no necesita Python) y `LEEME.txt`. Sin datos
personales y CON `roleplay/datos` (los corpus; el script verifica las dos cosas). Empaquetada,
los datos van a `%APPDATA%\EAFC26 Roleplay`; la clave de IA es opcional (cada amigo la suya). `build/` y `dist/` estan
en `.gitignore`.

Doble click: `files\EAFC Roleplay.exe` o el acceso "EAFC 26 Roleplay" del escritorio.
El .exe es un lanzador de 39 KB (`scripts/lanzador/Lanzador.cs`, compilado con el
`csc.exe` de .NET 4 que trae Windows) que abre `app.py` con `.venv\Scripts\pythonw.exe`:
corre siempre el codigo actual, no hay que recompilarlo al cambiar Python. Esta en
`.gitignore`; se regenera con `crear_acceso_directo.py` (tambien rehace `app.ico`).

No requiere `.env` ni clave. Las claves OPCIONALES de la IA (`groq_api_key` / `gemini_api_key`
en `ajustes.json`, o `GROQ_API_KEY(S)` / `GEMINI_API_KEY(S)` en el `.env` de la carpeta de datos;
varias separadas por coma) nunca se imprimen, loguean ni pegan. `ajustes.json` y `.env` estan en
`.gitignore` (el repo es publico).

## Arquitectura

Reorganizado el 2026-10-14 (antes eran 18 archivos sueltos en la raiz; respaldo
del original en `Proyecto Fifa\respaldo-files-2026-10-14.zip`).

| Archivo | Rol |
|---|---|
| `app.py` | Unico entry point; argumento opcional para abrir un modulo suelto. Icono de ventana, AppUserModelID (barra de tareas) y `sys.excepthook` -> `errores.log` + QMessageBox (con pythonw no hay consola) |
| `roleplay/config.py` | Rutas. Recursos desde la carpeta del codigo; DATOS (`DB_PATH`, `ajustes.json`, `errores.log`, `garage/`, `navegador/`) en `CARPETA_DATOS`: raiz del proyecto corriendo desde codigo, `%APPDATA%\EAFC26 Roleplay` empaquetada, o `EAFC_ROLEPLAY_DATOS` si esta en el entorno |
| `roleplay/ajustes.py` | `ajustes.json` de cada persona (`juego` elegido a mano, `en_vivo`...); leer nunca falla |
| `roleplay/diagnostico.py` | `revisar()`: modo, motor narrativo (cuantos archivos en `roleplay/datos`), IA hibrida (`ia.estado()`: cuantas claves, sin mostrarlas), base, juego, microfonos, una captura de prueba (solo el tamano), navegador |
| `roleplay/datos/` | **Los datos del motor narrativo** (JSON, sin tildes; los emojis si van): `corpus_entrevista.json` (preguntas de los 3 periodistas, reacciones, previa), `corpus_prensa.json` (titulares/cuerpos por hito, cruces `x_*`, mundo: solo hechos reales), `corpus_redes.json` (comentarios por tipo y tono, autores, posts sugeridos por personalidad), `corpus_vida.json` (backstory y ganchos), `lexico.json` (5 ejes con pesos por palabra/frase, negaciones, promesas), `jugadores_fc26.json` / `competiciones_fc26.json` (nombres por id de EA CON fecha de nacimiento: si la de la partida no calza, es otra persona y queda sin nombre; se suman con `scripts/nombres_faltantes.py --agregar`). Claves que empiezan con `_` son comentarios |
| `roleplay/servicios/ia.py` | **IA hibrida opcional** (solo `urllib`): `pedir_json(sistema, usuario, esquema, timeout=6)` -> dict o None, NUNCA lanza. Cascada: Groq `llama-3.3-70b-versatile` (429/5xx -> `llama-3.1-8b-instant`; 400/401/403 -> la siguiente clave) -> Gemini REST `gemini-2.5-flash` -> `-flash-lite` -> None (toda la cascada a lo sumo 2x timeout). `REGLAS` en cada pedido: no inventar datos ni nombres reales. Apagada con `sin_ia` en ajustes o `EAFC_SIN_IA=1` (lo pone `tests/ayuda.py`). `probar()` (boton de Ajustes), `estado()` (diagnostico), y piezas: `texto` (limpia y acota), `entero` (acota), `ficha`, `describir_cruces`, `comentarios_validos`, `cita_literal` (la cita solo vale si son palabras textuales del jugador). Quien la usa: `entrevista.preguntas_con_ia` / `reaccion_con_ia` (tambien la previa), `instagram._comentarios_con_ia`, `hinchada._comentarios_con_ia` (una llamada para todos los eventos; los que falten, del corpus) y `prensa._nota_con_ia`. Siempre DESPUES de calcular lo local, que queda de respaldo |
| `roleplay/servicios/narrador.py` | **Motor de gramaticas**: `Narrador(*corpus, usados=, dado=, ricas=)`: `decir(simbolo, **datos)` (texto nuevo, anotado), `elegir()` (pieza sin anotar), `puede()`, `tiene()`. Alternativas con `{variable}` (solo entran si estan todos los datos) y `#simbolo#` (recursivo). Anti-repeticion: por simbolo los ultimos bloques (min(40, n-1): siempre queda uno libre) + huellas de los ultimos 40 textos; si sale uno reciente se rearma sorteando entre TODAS las piezas (con la rueda, dos piezas iguales rotan en fila). `narrador(player_id, *corpus)` (context manager) carga/guarda `estado_json.narrador_usados`; sin perfil (o borrado), sin memoria. `unir()`/`limpiar()` (espacios, mayuscula tras punto) |
| `roleplay/servicios/lexico.py` | **Evaluador lexico**: `puntuar(texto)` (5 ejes: humildad_equipo, amor_hinchada, ego_confianza, excusa_polemica, ambicion_foco; tildes y mayusculas no importan; una negacion en las 2 palabras previas invierte el peso), `leer(respuestas) -> Lectura` (eje dominante o `neutro` bajo 1.5, intensidad, `cita` = la oracion mas jugosa recortada a 150, `promesa`, palabras) |
| `roleplay/servicios/cruce.py` | **Estado cruzado**: `cruces(player_id, rival=, rating=, carrera=)` -> lista de `Cruce(tipo, peso, datos)` del mas jugoso al menos: compra cara (>= 150.000, ultimos 45 dias; con rating < 6.2 `compra_mal` con modelo y precio), pareja real/famosa/rumor/crisis, meta cerca (con la partida, lo que lleva HOY) o complicada, ex club (traidor/idolo/mala salida), hinchada en contra/idolo, evento reciente (21 dias). Solo lee. Importa `metas` adentro de la funcion (ciclo metas -> partida_real -> prensa -> cruce) |
| `roleplay/models.py` | Dataclasses `PlayerProfile`, `MatchInterviewRecord`, `NoticiaPrensa`, `InstagramPost` + catalogos del quiz |
| `roleplay/database.py` | SQLite. Mapeo GENERICO dataclass <-> fila (`TABLAS`, `_insertar`, `_desde_fila`); `_editar_estado` para leer-modificar-escribir `estado_json` en una transaccion |
| `roleplay/servicios/backstory.py` | `generar_backstory(perfil, dado=)`: 3 parrafos (origen, personalidad+motivacion, vida personal+anecdota+cierre) con `ricas=True` (prefiere las alternativas que usan mas datos del quiz) + 3-4 ganchos distintos |
| `roleplay/servicios/entrevista.py` | **Tres periodistas** (`PERIODISTAS`): Ignacio Ferrada (Pizarra Tactica: numeros, tabla, racha), Valentina Aros (Radio Tribuna: vestuario, hinchada, metas, ex club) y Rocco Salinas (El Picante: compras, pareja, eventos, contradicciones). `generar_entrevista(perfil, stats)`: cada uno elige la pregunta de mas prioridad que el corpus pueda escribir; `_memoria()` mira las ultimas 10 entrevistas (sequia rota >= 3, racha, caida de nota, mismo rival antes, contradiccion: ego la fecha pasada y hoy derrota) y `_tabla()` la tabla antes/despues del partido. `evaluar_respuestas()`: `lexico.leer` -> delta (BASE por eje x resultado, intensidad, personalidad, rating, respuestas secas, promesa; tope ±15), `delta_carino` (lo aplica la sala a `clubes.sumar_carino`), cita y gancho si prometio algo. `reaccionar()` = apertura + nucleo + cruce + cierre |
| `roleplay/servicios/prensa.py` | Hitos deterministas (rachas, goles, rating ultimos 5) + noticias del motor: `noticia_de_hitos` (apertura + un nucleo por hito + un cruce `x_*` + cierre), `noticia_de_entrevista` (la cita entre «», una vez por entrevista: `estado_prensa.entrevista_reportada`), `noticia_del_mundo(hecho)` (dict de partida_real o texto suelto). Nada inventado: si no paso nada real, no hay noticia. `revisar_prensa` no falla ni espera. `calcular_estadisticas_acumuladas` tambien alimenta la carta del Resumen |
| `roleplay/servicios/instagram.py` | `generar_reaccion_post(perfil, texto, rep, seg)`: lee el post con `lexico` (humilde/hinchada suma; ego/polemica junta de todo y con reputacion < 40 resta), comentarios del corpus y likes >= 0; `sugerir_post(perfil, ultimo_partido)` por personalidad y resultado. `ComentarioIA`/`InstagramReaccionIA` quedaron con el nombre viejo |
| `roleplay/servicios/vision.py` | Solo `MatchStats`. `extraer_stats_partido` lanza RuntimeError: leer la captura de fin de partido necesitaba IA y no hay forma confiable sin ella (quedan "Cargar de mi partida" y escribir las stats a mano) |
| `roleplay/servicios/captura.py` | Captura con dxcam en BGRA + PNG con Qt: **sin OpenCV** (se saco el 2026-10-14). Hoy solo la usa el diagnostico |
| `roleplay/servicios/juego.py` | Encontrar FC 26 (elegido a mano > Steam > EA app > Epic; registro inyectable) y abrirlo con `os.startfile` por su plataforma |
| `roleplay/servicios/accesos.py` | Los dos iconos del escritorio (.url para URLs, .lnk via WScript.Shell por PowerShell) |
| `roleplay/servicios/audio.py` | Voz: `listar_microfonos` (solo la API de audio por defecto), `GrabadorMicrofono` (WAV mono 16 kHz, tope 120 s, `crear_stream` inyectable), `transcribir(wav, pregunta)`: **offline** con System.Speech de Windows (`GUION_RECONOCER` por PowerShell, `DictationGrammar` sobre el WAV temporal que se pasa en `EAFC_WAV`, `CREATE_NO_WINDOW`, se borra al terminar). Codigo 3 = no hay reconocedor en espanol (`SIN_RECONOCEDOR` explica como agregarlo). En el PC de Simon esta es-ES "Microsoft Speech Recognizer 8.0" |
| `roleplay/partida/formato.py` | Bytes del guardado de FC 26 -> registros (bases de datos de EA, secciones `teams`/`stagadv`/`stndgs`/`compavg`). Valida todo; si algo no calza, `FormatoDesconocido` |
| `roleplay/partida/carrera.py` | `construir(datos) -> Carrera`: equipos, competiciones, partidos, `actuaciones_en(partido)` (quien jugo/marco, de los ultimos 5 partidos de cada jugador), `tabla()` calculada con los resultados, `goleadores()`, `ficha(jugador)`. Los codigos de tablas/campos de FC 26 estan arriba del archivo |
| `roleplay/partida/lector.py` | `carrera_actual()`: el `CmPlr*` mas reciente (o el elegido en Ajustes) de `%LOCALAPPDATA%\EA SPORTS FC 26\settings`, con cache por fecha/tamano. Solo lee. `EAFC_FC26_GUARDADOS` cambia la carpeta |
| `roleplay/servicios/partida_real.py` | Lo que la app hace con la partida: `ultimo_partido()` (stats del ultimo partido; asistencias/tarjetas/figura por diferencia con la lectura anterior, `estado_json.partida`), `hechos_destacados()` (hat-trick > goleada > choque de punta, elegidos por codigo) y `hecho_para_prensa()`/`premio_para_prensa()`/`mercado_para_prensa()` (el hecho como dict con sus datos sueltos para el titular), `revisar_prensa_con_partida()`, `resumen_temporada()`, `leer_para_entrevista()`. `nombres_de_jugadores()`: editados en la partida > base local; el resto se describe. La tabla `nombre_conocido` (lo que adivino la IA en versiones viejas) ya NO se lee |
| `roleplay/servicios/identificar.py` | Nombres desde `roleplay/datos/jugadores_fc26.json` y `competiciones_fc26.json` por id de EA. Si la base trae el nacimiento y no calza con la ficha, nombre vacio (otra persona). **Nunca inventar nombres** |
| `roleplay/ui/vigilante.py` | **Modo en vivo**: `VigilantePartida` mira el guardado cada 5 s (sin abrirlo); si cambio y se asento, lo lee en un hilo. `partido_nuevo` si el club del usuario jugo un partido que no se aviso (`estado_json.partida.avisado`; la primera lectura solo marca); si no, `dia_nuevo` cuando avanzo la fecha del juego (`partida.dia_visto`: jugaron otros). Ajustes `en_vivo.vigilar` / `en_vivo.preguntas_solas` |
| `roleplay/ui/overlay.py` | `SalaFlotante`: panel semitransparente siempre encima (Tool + Frameless + StaysOnTop, `WA_ShowWithoutActivating`: no le quita el foco al juego). Es un ESPEJO de la sala de prensa: lee su estado al recibir `InterviewWindow.cambio` y sus botones llaman a los de la sala (una sola entrevista). **Bimodal**: HUD (`mostrar()`, `WindowTransparentForInput`: mouse y teclado pasan al juego; `avisar(titulo, texto)` muestra un aviso 9 s y, si estaba escondida, aparece compacta (`cuerpo` oculto) y se esconde sola) e interactivo (`atajo_presionado()` / `modo_interactivo()`: guarda la ventana del frente (`GetForegroundWindow`), toma el foco; `modo_hud()` o "Volver al juego" le devuelve el foco con `SetForegroundWindow`). Cambiar el flag esconde la ventana: `_aplicar_modo` la vuelve a mostrar. Sin el atajo (`click_a_traves=False`) nunca deja pasar los clicks. Las llamadas a Windows solo con la plataforma "windows" (no en offscreen). El menu manda avisos de partido nuevo, dia nuevo (si esta a la vista), auto entregado, evento inesperado y prensa (`_avisar_encima`: con "flotante" prendido y la app sin foco) |
| `roleplay/ui/atajo.py` | `AtajoGlobal`: Ctrl+Shift+F12 con `RegisterHotKey` (ctypes) + `QAbstractNativeEventFilter`. Ojo: el tipo de evento llega como QByteArray (comparar con `bytes(tipo)`). Si la combinacion esta tomada, `registrar()` da False y la app sigue |
| `roleplay/ui/comun.py` | `ejecutar_en_hilo`, `esc` (escape HTML), `miles`, `fecha_corta`, `con_scroll` (pagina transparente) |
| `roleplay/ui/estilos.py` | Tema oscuro estilo EA FC: colores (unico lugar), `fuente_titulo()`, QSS, paleta forzada |
| `roleplay/ui/componentes.py` | `icono()` (SVG propios coloreados), `titulo_pagina`, `titulo_seccion`, `Tarjeta`, `Mosaico`, `chip`/`chip_tono`, `chip_alternable`, `fila` (None = estirable), `CartaJugador` (carta FUT pintada; nivel por reputacion: bronce <45, plata, oro >=70, elite >=85), `Avatar`, `FondoEstadio`, `agregar_noticia`, `limpiar_layout` |
| `roleplay/servicios/economia.py` | Vida y patrimonio: el sueldo real (`Carrera.sueldo_usuario`, campo `cmGX` de `mPrV`) se acredita con los dias del juego (`acreditar()`, neto 55%; la primera vez, lo cobrado desde el 1 de julio), catalogo sin marcas (casas, autos, relojes, moda, yate, jet) y donaciones; `efecto()` decide seguidores, reputacion, si es noticia y el tono (donar suma; presumir en mala racha resta, mas si es humilde/reservado); `repercusion()` (hilo) arma la noticia y los comentarios con `eventos.contar`. Todo en `estado_json.economia` |
| `roleplay/servicios/autos.py` | El concesionario (`Modelo.url_configurador`: la web oficial de cada modelo, sacada de los botones "Configure" de cada marca el 2026-10-15; SF90 y Roma ya no se venden y van al configurador general de Ferrari, Lamborghini y Rolls-Royce eligen el modelo adentro, Bugatti no tiene configurador y va la pagina del Tourbillon): modelos de marcas REALES (solo el nombre como texto; decision de Simon: la app es entre amigos; nunca logos ni modelos 3D de las marcas), precio base aproximado, opciones con recargo (`precio()`), `describir()` y `Configuracion` (se guarda como dict en el pedido) |
| `roleplay/ui/configurador.py` | `Configurador` (QDialog): a la IZQUIERDA la web oficial de la marca adentro de la app (`crear_navegador` -> `ui/navegador.py`), a la DERECHA el panel del juego (pintura, llantas, pinzas, franjas, interior, extras, patente, precio y PEDIR). La foto del garage: "CAPTURAR VISTA" (con `RecortarFoto` para quedarse con el auto), "Pegar imagen" del portapapeles, o se saca sola al pedir; `guardar_foto` la deja en `config.CARPETA_GARAGE` (<id del pedido>.jpg, 960 de ancho) y `miniatura()` la muestra en Vida (o el dibujo si no hay foto). Sin navegador (sin pantalla, o sin QtWebEngine) queda el dibujo: `svg_auto(config)` con `SILUETAS`, 14 carrocerias **calcadas a mano de fotos reales de perfil** (el archivo de origen va en un comentario arriba de cada una). Solo el contorno: nunca logos ni modelos 3D de las marcas ni de GTA. **QtSvg no soporta clip-path**: franjas y fibra van como cortes del degradado (`_pintura`), y los parantes se cortan contra la ventana (`_ventana_en`). Con la pantalla al 300%, las imagenes se escalan con `_nitida` (si no, se ven a un tercio) |
| `roleplay/ui/navegador.py` | El navegador integrado (QtWebEngine): `Navegador(url)` con atras, recargar y "abrir en tu navegador"; perfil persistente en `<datos>/navegador` (el aviso de cookies se contesta una vez); los enlaces a otra ventana se abren en la misma; `foto()` devuelve lo que se ve en pixeles de verdad. **Se importa recien al abrir el configurador** (TestArranque vigila que abrir la app no cargue QtWebEngine) y `app.py` pone `AA_ShareOpenGLContexts` antes de crear la QApplication. **No se tocan encabezados de seguridad**: la web es la pagina principal (no un iframe), asi que X-Frame-Options/frame-ancestors no aplican. Sin pantalla (offscreen, las pruebas) `disponible()` es False: Chromium no dibuja y la foto saldria en blanco (tampoco con la ventana oculta: para probarlo de verdad, una ventana visible fuera de la pantalla) |
| `scripts/trazar_silueta.py` + `docs/siluetas.md` | Como se calca un auto nuevo: buscar la foto de perfil en Commons, medirla en el navegador (`medirAuto` automatico o la rejilla `ver()` a mano), y `trazar_silueta.py medidas.json --puntos --insertar <modelo> --fuente "..."` la pega en `SILUETAS`. Endereza la perspectiva (`perspectiva`, `ejes_sobre_radio`) y achica la escala si el auto es mas alto que el dibujo (G 63). Las medidas de cada auto quedan en `docs/siluetas/*.json` |
| `roleplay/servicios/amor.py` | Vida sentimental (`estado_json.amor`). Arranca del personaje (`estado_relacion`, `nombre_pareja`): novia real -> en pareja; celebridad o soltero -> soltero (la famosa es mas probable con "celebridad"). Sorteo semanal como los eventos (25%, semilla propia `amor:jugador:semana`): cena, tribuna, vacaciones (junio-julio), un viaje sorpresa, roces por tantos viajes, aniversario; con una famosa tambien alfombra roja, rumores de crisis, entrevista. **La novia real es una persona real**: solo momentos lindos o roces leves, nunca prensa del corazon, y lo negativo sale en tono neutral (sin titulares de "Polemica"). **Las famosas son INVENTADAS** (`NOMBRES` x `APELLIDOS` x `OFICIOS`): nunca personas reales. Decisiones: hacerlo oficial o negarlo, proponer casamiento (relacion >= 80 y 180 dias; el anillo cuesta 6 semanas), la boda (a los 120 dias: a lo grande o intima) y la crisis (< 25). Tarjeta "Vida sentimental" en Vida |
| `roleplay/servicios/clubes.py` | Tu hinchada: carino (0-100) de la hinchada de cada club (`estado_json.clubes`). Arranca en 50; cada partido del club lo mueve (ganar +1, perder -1, cada gol +2 hasta 6, nota >= 8 +2, < 6 -2) y los eventos inesperados tambien (`por_evento`). El club sale del CONTRATO (`club_de`), no de los partidos: un traspaso se ve apenas se firma. Al cambiar de club: salida como idolo (>= 70), normal o por la puerta de atras (<= 30); si eras idolo y te vas a un club de LA MISMA LIGA, traidor (-30; la partida no guarda rivalidades); volver a un club te recibe segun como te fuiste. Decisiones (`DECISIONES`): hinchada en contra (< 25), polemica (despues de la polemica en redes o la fiesta del yate) y un grande que pregunta por el idolo (>= 85 y reputacion >= 70, una vez por temporada); `elegir()` mueve carino, reputacion y seguidores y puede traer un reto. Se contestan en el Resumen (tarjeta "Tu hinchada"); todo es noticia via `eventos.contar()` |
| `roleplay/servicios/eventos.py` | Eventos inesperados, buenos y malos (multa con su auto, choque, robo en su casa, fiesta filtrada en el yate, gripe, molestias, multa del club, polemica en redes, hinchas que lo increpan; campana publicitaria, video viral, visita a un hospital, TV, jugador del mes, la camiseta a un nene). `revisar()` sortea una vez por SEMANA del juego (30%, semilla jugador+semana: la misma partida da los mismos eventos), a lo sumo uno por revision, con reglas (`requiere`: auto/casa/yate/mala_racha/buena_racha/reputacion:N; `pesos` por personalidad; no repite los ultimos 4). El codigo decide reputacion, seguidores (la escala de la hinchada) y plata (semanas de sueldo neto); `contar()` (hilo; la usan tambien la economia, la hinchada y el amor) arma noticia (`t_vida_<tono>` + la descripcion + `c_vida_<tono>`) y comentarios. Algunos traen un `reto` de roleplay (arrancar en el banco, no jugar el proximo): la app no toca el juego, es una propuesta. `estado_json.eventos` |
| `roleplay/ui/vida.py` | `PaginaVida`: saldo, sueldo neto, gastos fijos, patrimonio; tienda por categoria, lo que tenes (vender al 70%), filantropia y movimientos. `acreditar_con(carrera)` la llama el menu en cada autoguardado (cobra, entrega autos y sortea los eventos inesperados: tarjeta "Lo que te paso" y aviso en la bandeja con `evento_inesperado`). Los botones se identifican por la propiedad `articulo` (el objectName es el del estilo) |
| `roleplay/servicios/metas.py` | Metas de temporada que se propone el usuario (`estado_json.metas`: goles, goles en liga, asistencias, top N de la liga). `evaluar_metas()` las decide con la partida (contables apenas se llega; el puesto al terminar la liga; las de una temporada pasada fallan); las entrevistas y la prensa las conocen por `cruce.py` (la meta a punto de cumplirse o complicada). La prensa devuelve `resultado["metas"]` y la sala lo guarda con `database.actualizar_metas` (que no revive una meta borrada) |
| `roleplay/servicios/mercado.py` | Fichajes reales: `clubes_de_jugadores(carrera)` (hombres, club de hoy) contra la foto anterior de la misma partida (tabla `club_visto`, `database.get/guardar_clubes_vistos`) -> `detectar_traspasos()` (noticia: tu club, media >= 82, o tu liga con media >= 75), `traspaso_del_usuario()` (hito `nuevo_club`). La foto se guarda recien despues de armar la prensa: si algo falla, se detectan de nuevo |
| `roleplay/servicios/previa.py` | Conferencia PREVIA al proximo partido: `previa_del_proximo(carrera)` arma los datos reales (tabla de los dos, rachas, ultimo partido del rival, cruces de la temporada, goleador rival; `ya_hecha` con `estado_json.partida.previa`), `generar_previa` / `evaluar_previa` (los mismos periodistas y el mismo evaluador; `BASE_PREVIA` sin resultado, delta acotado a ±10, titular con la cita si hay) y `noticia_de_previa`. NO se guarda como partido (no suma PJ ni goles) |
| `roleplay/servicios/temporada.py` | `vista_temporada(carrera, competicion)`: lo que muestra la pagina Temporada (tabla con el club marcado, goleadores con el jugador del usuario marcado, resultados y proximos del club, la ultima fecha). Liga primero; una competicion ajena cae en la del club |
| `roleplay/ui/temporada.py` | `PaginaTemporada`: chips para elegir competicion, tabla (QGridLayout de QLabel; la fila del club lleva un QFrame resaltado DEBAJO, en la misma celda), goleadores, tus partidos y la ultima fecha. Si se cambia de competicion mientras lee, vuelve a leer al terminar |
| `roleplay/ui/menu.py` | `MainMenuWindow(pagina_inicial)` (lateral con JUGAR FC 26 y AJUSTES + `FondoEstadio`) + `PaginaResumen` (carta, mosaicos, historia, tramas, central de noticias) |
| `roleplay/ui/ajustes.py` | `DialogoAjustes` (juego, partida, modo en vivo, "Motor narrativo e IA hibrida": claves de Groq y Gemini en modo password, "Usar solo motor local", "Probar IA" en un hilo con proveedor y ms; iconos, diagnostico), `abrir_juego_o_preguntar`. Ya no hay bienvenida |
| `roleplay/ui/personaje.py` | `CharacterWizard` (ClassicStyle; titulos en rich text con "PASO n/8"; backstory editable o escrito a mano) |
| `roleplay/ui/entrevista.py` | `InterviewWindow` "Sala de prensa": marcador ("Cargar de mi partida" o a mano; no hay captura) -> preguntas de los 3 periodistas (cada una con boton de voz) -> reaccion -> prensa. Despues de evaluar, `_mover_carino()` aplica `delta_carino` a la hinchada del club |
| `roleplay/ui/instagram.py` | `InstagramWindow`: perfil (avatar + mosaicos), nuevo post, resultado, "Tus hinchas" (actividad sin publicar) y feed en tarjetas. `revisar_hinchada()`: una a la vez; si se pide otra mientras corre, se hace al terminar |
| `roleplay/servicios/hinchada.py` | El Instagram que se mueve solo: `eventos_nuevos()` (partidos del usuario y noticias sobre el desde `estado_json.hinchada`; la primera vez solo el ultimo partido), `crecimiento_por_partido/noticia()` (los seguidores los decide el codigo), `comentar_eventos()` y `comentarios()` (2-3 del corpus: el tono sigue a los seguidores, con algun gracioso o rival). Se guarda en la tabla `actividad_instagram` |
| `roleplay/ui/iconos/` | Flechas/check de la QSS (SVG) y `app.ico` (lo genera el script del acceso directo) |
| `scripts/seed_test_matches.py` | Siembra/borra partidos "Rival de prueba N" en el ultimo personaje (base REAL) |
| `scripts/crear_acceso_directo.py` + `scripts/lanzador/Lanzador.cs` | Icono, .exe lanzador (dev) y los dos iconos del escritorio |
| `scripts/empaquetar.py` + `scripts/LEEME_AMIGOS.txt` | Paquete PyInstaller + zip para amigos (`--add-data` de `ui/iconos` y `roleplay/datos`; `podar_chromium`) |
| `scripts/nombres_faltantes.py` | Lista los goleadores de las competiciones del usuario que no tienen nombre (id, club, posicion, seleccion, nacimiento) y `--agregar ID "Nombre"` los suma a `jugadores_fc26.json` con el nacimiento de la partida. **Solo nombres seguros**: el 2026-10-15 se verifico la base vieja contra la partida y la IA se habia equivocado en 8 de 20 (ej. el id de Vinicius Jr como Haaland; 851 era la Copa de Francia, no la Ligue 1) |
| `tests/` | `ayuda.py` (base temporal, dialogos mudos, `texto_de_noticias`) + `test_*.py`; `test_narrador.py` prueba el motor (gramatica, cola de 40, corpus completos y sin tildes, lexico, cruces, memoria de entrevistas, backstory) |

## Convenciones (respetarlas)

- **Modo en vivo**: ante un partido nuevo, `MainMenuWindow._on_partido_nuevo` avisa en la
  bandeja de Windows (QSystemTrayIcon), marca "Entrevistas ●", la sala lo carga y genera
  las preguntas si esta libre (`InterviewWindow.ocupada()`: nunca pisar una entrevista a
  medias) y corre la prensa. `set_estado_partida` MEZCLA claves (no reemplaza).
  Ante un `dia_nuevo` (autoguardado sin partido del usuario), `_on_dia_nuevo` le pasa la
  partida a la sala y corre la prensa (solo hechos reales: la prensa nunca inventa
  noticias). Toda revision de prensa emite `noticias_publicadas`: el
  menu avisa en la bandeja (solo las automaticas, con la ventana sin foco) y los hinchas
  reaccionan.
- **Sala flotante**: toda accion nueva de la sala de prensa que cambie lo que se ve debe
  emitir `self.cambio` (o pasar por `_refrescar_botones`, que lo emite), o el panel no se
  entera. El panel nunca hace logica propia.
- **Hitos reales** (`detectar_hitos_reales`, en `estado_prensa.reales`): goles de la
  temporada (se reinician por temporada, julio a junio), maximo goleador, partidazo,
  liderato ganado/perdido, campeon. Se suman a los hitos del historial de entrevistas.
- **La partida de FC 26 se LEE, nunca se escribe** (y no se toca el juego). Los numeros
  (resultados, goles, tablas, quien es noticia) los decide el codigo; los nombres que la
  partida no trae salen de la base local (`roleplay/datos`). Un nombre que no esta (o cuyo
  nacimiento no calza) va vacio y el jugador se describe ("el delantero centro del
  Arsenal"): nunca inventar.
- **El juego nunca se toca**: ni archivos, ni memoria, ni inyeccion. Se abre por su
  plataforma (`os.startfile` de la URL/acceso) y la app solo lee su guardado. Por eso no
  lo rompe, las actualizaciones del juego no la rompen y se puede jugar online.
- **Textos nuevos = corpus, no codigo**: una frase nueva va en `roleplay/datos/corpus_*.json`
  (sin tildes, `{variables}` que el codigo pase y `#simbolos#` que existan: `test_narrador.py`
  lo revisa). El codigo elige el SIMBOLO (que es noticia, que pregunta, que tono) y pasa los
  datos; nunca arma frases con f-strings para mostrar como prensa. Todo lo que se escribe
  para un jugador va con `narrador(perfil.id, ...)` (memoria anti-repeticion); `decir()`
  para el texto final, `elegir()` para piezas que se juntan con `unir()`.
- **Nada de texto "para la IA"** en lo que se muestra: los `detalle`/`descripcion` de
  eventos, compras y amor terminan TAL CUAL en el cuerpo de la noticia (en tercera persona,
  despues del nombre). Ya paso: la consigna "tratarla con respeto" iba a salir impresa.
- `dxcam`, `cv2`, `sounddevice` y QtWebEngine se importan DENTRO de las funciones
  (arranque 1,9 s -> 0,35 s). `tests/test_ui.py::TestArranque` falla si alguien los
  vuelve a importar arriba (y si alguien importa `google.genai`). Los microfonos se
  listan recien al mostrar preguntas.
- **Todo lo lento desde la UI usa `ui.comun.ejecutar_en_hilo(func, *args,
  al_completar=metodo, al_fallar=metodo)`** (leer la partida, revisar la prensa, evaluar).
  Nada de clases QThread nuevas ni de guardar el hilo en un atributo: el registro
  `_TareasVivas` lo mantiene vivo hasta que termina. Pasar METODOS de la ventana, no
  lambdas (PySide desconecta los metodos si la ventana se destruye).
- Lo que corre en un hilo y vuelve despues se guarda contra el jugador/datos de ESE
  momento (ver `_evaluando`, `_prensa_player_id`, `_publicando`), no contra
  `self.perfil` ni el formulario actual.
- Botones de la entrevista: solo `_refrescar_botones()` decide cuales estan activos
  (incluye grabando/transcribiendo: mientras hay voz en curso no se regenera ni se envia).
- Todo texto del motor o del usuario que va a un QLabel con formato pasa por `esc()`;
  un `<3` sin escapar se comia el resto del comentario.
- Numeros con separador de miles: `miles(n)`; contadores cortos: `compacto(n)` (1,5K).
- **Estilo**: colores y fuentes solo en `estilos.py`; piezas en `componentes.py`. Los
  titulos/numeros grandes usan `fuente_titulo(px)` por codigo (el espaciado entre letras
  no existe en QSS). La QSS **no** puede poner `font-family`/`font-size` a `QWidget`:
  pisa todo `setFont()` (pasó: los titulos salian con letra chica). La fuente base va
  con `app.setFont()`. Textos de UI en MAYUSCULA en botones/titulos (como el FC).
- Las paginas van dentro de `con_scroll` y son transparentes: el fondo lo pinta
  `FondoEstadio`. Para reemplazar contenido usar `limpiar_layout` (esconde antes de
  `deleteLater`; si no, lo viejo se ve encima de lo nuevo hasta la proxima vuelta).
- Lo que genera la app queda **editable** antes de guardarse (backstory, ganchos, stats,
  transcripciones).
- Estado de modulos nuevos va en `player_profile.estado_json` (ej: `reputacion_actual`,
  `historial_reputacion`, `prensa`, `seguidores_instagram`) para no migrar el esquema.
  Columnas nuevas reales: agregarlas al `SCHEMA` **y** a `COLUMNAS_AGREGADAS`
  (la DB del usuario ya existe y tiene datos). Un campo nuevo en un dataclass necesita
  su columna: el mapeo generico falla fuerte si falta.
- Las paginas del menu exponen `actualizar()`, que recarga el perfil; el menu lo llama al navegar.
- Strings de UI en espanol (voseo/chileno informal), sin tildes en el codigo ni en los corpus.
- Nunca inventar nombres de personas/jugadores reales, ni noticias: la prensa solo
  escribe sobre lo real (hitos, la cita de la entrevista, hechos/premios/mercado de la
  partida; si no paso nada, no hay noticia). Las famosas de la vida sentimental si son
  inventadas (nunca personas reales).

## Testing

`.venv\Scripts\python.exe -m unittest discover -s tests` (328 pruebas, ~20 s). `tests/ayuda.py`:
- Fija `EAFC_FC26_GUARDADOS` a una carpeta vacia: las pruebas no leen la partida real.
- Fija `EAFC_SIN_IA=1`: ninguna prueba sale a internet. Las de la IA (`test_narrador.py`, clase `ConIA`)
  la prenden con `urlopen` mockeado (`self.red`: respuestas o excepciones en orden) y fallan si sale una
  llamada que no se esperaba.
  `tests/fabrica_partida.py` arma un guardado FALSO con el mismo formato (para todo lo de
  `roleplay/partida`). `TestPartidaRealDelPC` lee la partida real si existe (solo lectura,
  exige que >90% de los marcadores cuadren con los goles de los jugadores); si no, se salta.
- Fija `EAFC_ROLEPLAY_DATOS` a una carpeta temporal ANTES de importar `roleplay`: ni las
  pruebas ni sus subprocesos escriben en la carpeta del proyecto.
- `PruebaConBase`: base temporal por prueba (`config.DB_PATH` parcheado).
- `PruebaDeInterfaz`: + QApplication offscreen + `QMessageBox.information/warning` mudos (en `self.avisos`).
- El motor narrativo corre DE VERDAD en las pruebas (es local): se prueba lo que sale
  (titular con el apellido o el modelo del auto, `hitos`, `tono`, que no queden `{}` ni
  `#simbolos#` sin expandir, que no se repita), no se mockea. El perfil tiene que estar
  guardado para que la memoria (`narrador_usados`) quede. Para ver que hechos llegan a la
  prensa, espiar `prensa.noticia_del_mundo` (ver `test_mercado.py`). Las pruebas con azar se
  corrieron 30 veces seguidas sin fallar; si una nueva depende del azar, pasarle `dado`.
- Voz: `audio.subprocess.run` mockeado (ver `test_audio.py`): nunca correr el reconocedor real.
- Microfono: `GrabadorMicrofono(crear_stream=StreamFalso(...))` (ver `tests/test_audio.py`);
  nunca grabar el microfono real en una prueba.
- `esperar_tareas()` en vez de `hilo.wait()` + `processEvents()`.
- `correr_aislado(codigo)`: para escenarios que, si fallan, cierran el proceso
  (QThread destruido corriendo => exit 127 sin mensaje).
- **Revisar como se ve**: las pruebas no ven el diseño. Capturas reales sin abrir
  ventanas: `ventana.setAttribute(Qt.WA_DontShowOnScreen)`, `show()`, asentar con
  varias vueltas de `processEvents()` + `sendPostedEvents(None, QEvent.DeferredDelete)`
  y `grab().save(...)`. Hacerlo sobre una COPIA de la base. (Con `QT_QPA_PLATFORM=offscreen`
  no hay fuentes de Windows salvo con `QT_QPA_FONTDIR=C:/Windows/Fonts`.)
- Paquete: probarlo como amigo nuevo con `EAFC_ROLEPLAY_DATOS=<carpeta vacia>` y
  `"dist\EAFC Roleplay\EAFC Roleplay.exe" --diagnostico`.
- No probado automaticamente: la IA con claves reales (Groq/Gemini), microfono real, el reconocedor de voz real y abrir el juego
  de verdad (`os.startfile` va mockeado; no lanzar FC 26 en el PC de Simon sin preguntar).

## Gotchas conocidos

- Windows en modo oscuro deja labels invisibles si no se fuerza la paleta (por eso `estilos.py`).
- Paths en PowerShell: `.venv\Scripts\python.exe`, no `/c:/...`.
- Los heredoc de Bash con caracteres no ASCII (°, «, emojis) cortan el script ("unexpected
  EOF"): para parchar archivos con esos caracteres, escribir el script a un archivo y correrlo.
- Ciclo de imports: `metas -> partida_real -> prensa -> cruce -> metas`. Por eso `cruce`
  importa `metas` adentro de `_meta`, y `partida_real` importa `metas`/`previa` adentro.
- dxcam convierte colores con OpenCV SALVO que se pida `output_color="BGRA"` con
  `processor_backend="numpy"`: asi se saco OpenCV (110 MB). PyInstaller necesita
  `--collect-submodules dxcam` (carga sus procesadores con `import_module`).
- Si la pantalla esta apagada, dxcam y Qt devuelven imagenes negras (no es un bug).
- `Path.write_text("a\r\n")` en Windows escribe `\r\r\n`: usar `newline="\r\n"`.
- PowerShell 5 lee UTF-8 sin BOM como ANSI ("Â·" en pantalla): el archivo esta bien.
- Microfono: Windows lista cada mic una vez por API de audio (32 entradas en el PC de
  Simon, 4 en MME); `listar_microfonos` deja solo la API por defecto. Si falla al abrir:
  Configuracion > Privacidad y seguridad > Microfono > apps de escritorio. MME corta
  los nombres a 31 caracteres.
- `QWizard` en Windows usa AeroStyle por defecto, que pinta zonas blancas: va ClassicStyle.
- QSS con Fusion deja los spinbox sin flechas: se dibujan con `iconos/flecha_*.svg`.
- Los hitos de rating (buen/mal momento) exigen 5 partidos: antes, con 0 partidos el
  promedio era 0.0 y salio una noticia falsa de "mal momento" (se borro de la base de
  Simon el 2026-10-14 y se reinicio el marcador; respaldo previo en
  `Proyecto Fifa\respaldo-db-antes-de-limpiar-2026-10-14.db`).
- Hay una copia vieja identica del codigo original en `C:\Users\canal\Documents\files`.

## Estado / roadmap

Hecho:
1. Quiz de personaje + backstory editable (o escrito a mano)
2. Entrevistas post-partido (stats de la partida o a mano; respuestas escritas
   o por voz; reaccion + reputacion evolutiva)
3. Prensa: hitos del jugador + noticias generales del mundo
4. Instagram: posts, comentarios, likes, seguidores
5. Interfaz estilo EA FC (tema oscuro, carta FUT por nivel de reputacion, scroll por pagina)
6. Lanzador .exe + icono + acceso directo; pruebas automaticas (unittest)

Hecho tambien: iconos "EA FC 26" / "EA FC 26 + Roleplay", boton JUGAR, Ajustes con
diagnostico, el paquete para amigos (cada uno con sus datos en APPDATA) y
la lectura de la partida de FC 26 (ver arriba).

**Noticias inventadas: SACADAS el 2026-10-16** (pedido de Simon del 2026-10-15). Ya no existen `prensa.noticia_de_ambiente`, `PROBABILIDAD_NOTICIA_GENERAL` ni el kwarg `incluir_general` (ni `solo_hechos` en la sala), y del corpus se fueron `t_general`/`c_general`/`#club_ficticio#`/`#jugador_ficticio#`/`#ciudad_ficticia#`. Las que ya estaban en la base de Simon (categoria "general" con esos titulares) siguen ahi hasta que el diga si se borran: en `noticia_prensa` son las ids 2, 3, 4, 8, 9, 10 y 13 (la 7, el hat-trick de Grealish, parece de un hecho real y se deja).

**Evolucion en 4 pilares (pedida por Simon el 2026-10-15, en orden; correr la bateria
despues de cada uno y actualizar este archivo):**
1. **Sin IA: HECHO el 2026-10-15.** Motor de gramaticas + cola de 40, cruces, memoria
   de entrevistas, 3 periodistas, evaluador lexico de 5 ejes con negaciones, nombres de
   base local, backstory combinatorio, voz con System.Speech. La lectura de la captura se
   saco (no hay reemplazo confiable sin IA).
2. **Configurador con la web oficial: HECHO el 2026-10-15** (`Modelo.url_configurador`, `ui/navegador.py`,
   boton CAPTURAR VISTA o la foto sola al PEDIR, vinculada en `pedido["foto"]` -> `posesion["foto"]`). La foto queda en `garage/<id>.jpg` (no en
   `autos_comprados/<id>.png` como decia el pedido). Los encabezados de seguridad NO se
   tocan (no hace falta: la web es la pagina principal, no un iframe).
3. Tienda universal: **A MEDIAS (2026-10-15, se paro por el uso semanal de Simon)**. Hecha la
   logica: `servicios/tiendas.py` (TIENDAS con las 14 webs oficiales verificadas en el navegador;
   Xbox Design Lab es `xboxdesignlab.xbox.com`; NIVELES de precio; `SCRIPT_METADATOS` + `leer_metadatos`
   lee JSON-LD/OpenGraph y convierte a la moneda del juego, probado a mano en JamesEdition y Secretlab),
   `economia.articulo_libre` / `comprar(extra=)` / categorias tecnologia y muebles / `carpeta_de_foto`,
   `instagram.post_de_compra` (corpus `presumir_<personalidad>`), y en `eventos.contar` el titular ya no
   repite el apellido. FALTA: `ui/tienda.py` (DialogoTiendaReal, reusar la foto del configurador;
   `guardar_foto` con carpeta `compras/` y `config.CARPETA_COMPRAS`; `Navegador.ir(url)` y
   `runJavaScript`), en Vida el boton de las tiendas y "PRESUMIR EN INSTAGRAM" en "Lo que tenes",
   `InstagramWindow.precargar` (+ `InstagramPost.foto`, columna en COLUMNAS_AGREGADAS), el menu, las
   pruebas (`test_tiendas.py`) y la doc.
4. Overlay bimodal: **HECHO el 2026-10-16** (ver `ui/overlay.py`). Probado con pruebas (flags, avisos,
   modos); NO probado encima del juego real ni que Windows deje devolver el foco (requiere FC 26 en
   "ventana sin bordes").
5. **IA hibrida: HECHA el 2026-10-16** (pedido de Simon, revierte el "no volver a meter IA" del Pilar 1, pero
   como capa opcional encima del motor local; ver `servicios/ia.py`). No probada con claves reales.

Siguiente (decidido con Simon el 2026-10-14):
- **Overlay**: hecho (ver arriba). En pantalla completa EXCLUSIVA ninguna ventana se puede
  dibujar encima sin engancharse al render del juego, que es justo lo que vigila el
  anticheat: no hacerlo nunca; "ventana sin bordes" es el requisito.
- **Modo en vivo: HECHO el 2026-10-14** (`ui/vigilante.py`, hitos reales en la prensa).
- **Overlay ("sala flotante"): HECHO el 2026-10-14** (`ui/overlay.py`, `ui/atajo.py`).
  Falta probarlo encima del juego real (requiere FC 26 en "ventana sin bordes").
- **Instagram con contexto real + "Sugerir post": HECHO el 2026-10-14**.
- **Pagina Temporada (tabla, goleadores, tus partidos, ultima fecha): HECHO el 2026-10-14**.
- **Concesionario con configurador (marcas reales en texto): HECHO el 2026-10-14**. Se paga al pedir;
  `economia.entregar_pedidos()` lo entrega cuando la fecha del juego llega (lo llama `PaginaVida.acreditar_con` en
  cada autoguardado) y RECIEN AHI se aplica el efecto y sale la noticia (tipo de actividad "entrega"); el menu avisa
  en la bandeja. Los autos genericos viejos quedan en `economia.ANTERIORES` (solo para garages ya existentes).
  Las siluetas de los 22 modelos se calcaron de fotos reales el 2026-10-14 (ver `docs/siluetas.md`); el Cullinan
  comparte la del Range Rover y los McLaren la del 12C (misma linea).
- **Configurador con la web oficial de la marca: HECHO el 2026-10-15** (`ui/navegador.py`; lo pidio Simon). El zip de los amigos paso de 71 a 195 MB por Chromium; `scripts/empaquetar.py:podar_chromium` saca ~125 MB que no se usan (recursos de depuracion, devtools e idiomas salvo ingles y espanol; probado que la web carga igual). El diagnostico dice si el navegador esta completo.
- **Vida sentimental: HECHO el 2026-10-14** (`servicios/amor.py`, tarjeta en Vida; la sortea `PaginaVida.acreditar_con` en cada guardado, junto con los eventos).
- **Tu hinchada (reputacion por club) y decisiones: HECHO el 2026-10-14** (`servicios/clubes.py`, tarjeta en el Resumen; el menu la actualiza en cada guardado con `PaginaResumen.actualizar_hinchada`). Ojo: `Carrera.equipo_usuario()` sale del ultimo PARTIDO (tarda en ver un traspaso); para el club de hoy, `club_de()`.
- **Eventos inesperados: HECHO el 2026-10-14** (`servicios/eventos.py`). Las lesiones de la partida no se leen (no se encontro donde las guarda FC 26): las "lesiones" son eventos del roleplay con un reto.
- **Vida y patrimonio (economia + filantropia): HECHO el 2026-10-14** (`servicios/economia.py`, `ui/vida.py`).
  Sueldo real verificado: `cmGX` correlaciona 0,89 con la media en los contratos del plantel (`DvsP`).
- **Prensa en cada autoguardado e Instagram que se mueve solo: HECHO el 2026-10-14** (`dia_nuevo`,
  `servicios/hinchada.py`). Sin Live Editor: alcanza con el autoguardado de FC 26.
- **Temporada: otras competiciones de la partida (otras ligas, copas, Mundial): HECHO el 2026-10-14**
  (`VistaTemporada.otras` / `es_propia`; combo "Otras competiciones...").
- **Metas de temporada: HECHO el 2026-10-14** (tarjeta en el Resumen; `meta_cumplida` +4 / `meta_fallida` -4 de
  reputacion via `prensa.BONOS_REPUTACION`).
- **Trayectoria: HECHO el 2026-10-14**. Cada revision de prensa con la partida guarda
  `estado_prensa.temporada_en_curso` (`resumen_de_la_temporada()`); cuando el juego pasa a otra temporada,
  `archivar_temporada()` la mueve a `estado_prensa.trayectoria` (con los titulos de la vitrina), sale el hito
  `fin_de_temporada` (balance en la prensa) y el Resumen muestra la tarjeta "Trayectoria". La partida no guarda
  las temporadas pasadas de forma legible (`cPet`/`NgwF` tienen pistas, sin confirmar): se archiva desde ahora.
- **Mercado de fichajes real: HECHO el 2026-10-14** (`servicios/mercado.py`; formato en `docs/partida-fc26.md`:
  `qdZF` liga de cada equipo, `CZUM` media/potencial/genero/posicion). Hasta 2 noticias del mundo por revision
  (`prensa.MAXIMO_NOTICIAS_MUNDO`), por importancia: el premio que gano otro, el mercado, el partido destacado.
  Los ultimos traspasos quedan en `estado_prensa.mercado` y la pagina Temporada los muestra.
- **Premios reales: HECHO el 2026-10-14**. `premio_del_mes()` (partida_real.py): al pasar de mes en el juego,
  el que mas goles hizo en la liga (goles de la liga ahora menos `estado_prensa.mes.base`; lo del mes nuevo se
  descuenta con las ultimas actuaciones). Si la app no vio el mes entero, no premia: vuelve a contar.
  `liga_terminada()` (sin pendientes Y una rueda completa) dispara `campeon` y `maximo_goleador`.
  `prensa.BONOS_REPUTACION` -> `revisar_prensa()["delta_reputacion"]`, que aplica la sala de prensa.
  Los premios del usuario quedan en `estado_prensa.vitrina` y el Resumen los muestra (tarjeta "Vitrina").
- **Conferencia previa al proximo partido: HECHO el 2026-10-14** (modo de la sala de prensa: `InterviewWindow._modo` "post"/"previa"; la sala flotante lo refleja con `texto_contexto()`).
- **Leer la partida guardada: HECHO el 2026-10-14** (`roleplay/partida/`). La sala de
  prensa carga sola el ultimo partido, el Resumen muestra la temporada real y sincroniza
  el club, la prensa escribe sobre hechos reales con nombres de la base local. Formato y
  hallazgos en `files/docs/partida-fc26.md`. Ideas que siguen: hitos de prensa con los
  totales reales (no solo con las entrevistas), traspasos (tablas `YMgA`/`NgwF`/`TtHG`
  sin confirmar), contexto real en Instagram.
- **Datos del juego via Live Editor (descartado por ahora)**: script Lua para el
  "FC 26 Live Editor" de xAranaktu que exporte stats de partidos a un JSON que la app
  lee. Solo carrera offline: el Live Editor funciona desactivando el anticheat de EA
  (riesgo de cuenta si se entra online con el inyectado; contra los terminos de EA).
  No ayudar a evadir el anticheat; solo el script de lectura y el lado de la app.
  **Nunca** meterlo en los iconos ni en el paquete de los amigos (se le dijo a Simon:
  un icono "con Live Editor" seria repartir el juego con el anticheat apagado).
  Ojo: hay repos "FC26 Mod Manager" en GitHub que piden desactivar el antivirus: no usar.

Pendiente (ideas del usuario):
- ~~Reputacion por club + eventos de decision~~: hechos (ver arriba)
- ~~Economia / lifestyle~~ y ~~filantropia~~: hechos (ver arriba)
- ~~Eventos inesperados~~: hechos (ver arriba)
- ~~Vida sentimental~~: hecha (ver arriba)

## Como trabajar con Simon

- **Sincronizacion continua con GitHub**: Despues de completar y probar cualquier cambio o feature (cuando `unittest` pase en verde), hacer siempre `git add`, `git commit` descriptivo y `git push origin main` automaticamente para que el repositorio remoto en GitHub refleje siempre el estado exacto del codigo en tiempo real. Atajo que ademas revisa que no se cuele nada privado: `.venv\Scripts\python.exe scripts\sincronizar_git.py "mensaje"` (desde `files/`). Mientras no exista el remoto `origin`, el push queda pendiente (avisarle a Simon).
- Respuestas directas y practicas, en espanol.
- A veces implementa partes el mismo: antes de reescribir algo, revisar lo que ya hizo y
  preguntar si hace falta. Si pide revision, revisar y corregir bugs reales (con prueba que los demuestre).
- Entregar cambios probados; avisar explicitamente lo que no se pudo probar (microfono y voz reales, overlay encima del juego).
