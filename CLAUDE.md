# EAFC 26 Career Roleplay

App de escritorio (Python + PySide6) que agrega una capa de roleplay narrativo al
Modo Carrera Jugador de EAFC 26 **sin modificar el juego** (corre al lado, como
Discord/OBS: lee la pantalla, nunca archivos ni memoria del juego): creacion de personaje con backstory, entrevistas
post-partido (escritas o por voz), prensa espontanea, Instagram ficticio y reputacion
que evoluciona. Proyecto personal de Simon (estudiante de Ing. Informatica, Chile).
Corre en Windows, desde `C:\Users\canal\Desktop\Proyecto Fifa\files`, con un venv en
`.venv` (Python 3.11.9). Repo git en `Proyecto Fifa\` (rama `main`; identidad
configurada solo en este repo).

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

**Paquete para amigos**: `dist\EAFC Roleplay (amigos).zip` (~71 MB; carpeta 170 MB) con
`EAFC Roleplay.exe` (PyInstaller onedir, no necesita Python) y `LEEME.txt`. Sin datos
personales (el script lo verifica). Empaquetada, los datos van a
`%APPDATA%\EAFC26 Roleplay` y la primera vez pide la clave de Gemini de CADA amigo
(nunca repartir la de Simon). `build/` y `dist/` estan en `.gitignore`.

Doble click: `files\EAFC Roleplay.exe` o el acceso "EAFC 26 Roleplay" del escritorio.
El .exe es un lanzador de 39 KB (`scripts/lanzador/Lanzador.cs`, compilado con el
`csc.exe` de .NET 4 que trae Windows) que abre `app.py` con `.venv\Scripts\pythonw.exe`:
corre siempre el codigo actual, no hay que recompilarlo al cambiar Python. Esta en
`.gitignore`; se regenera con `crear_acceso_directo.py` (tambien rehace `app.ico`).

Requiere un `.env` en `files/` con `GEMINI_API_KEY=...` (o `GEMINI_API_KEYS=k1,k2`).
Nunca imprimir, loguear ni pegar la key en ningun lado.

## Arquitectura

Reorganizado el 2026-10-14 (antes eran 18 archivos sueltos en la raiz; respaldo
del original en `Proyecto Fifa\respaldo-files-2026-10-14.zip`).

| Archivo | Rol |
|---|---|
| `app.py` | Unico entry point; argumento opcional para abrir un modulo suelto. Icono de ventana, AppUserModelID (barra de tareas) y `sys.excepthook` -> `errores.log` + QMessageBox (con pythonw no hay consola) |
| `roleplay/config.py` | Rutas. Recursos desde la carpeta del codigo; DATOS (`DB_PATH`, `.env`, `ajustes.json`, `errores.log`) en `CARPETA_DATOS`: raiz del proyecto corriendo desde codigo, `%APPDATA%\EAFC26 Roleplay` empaquetada, o `EAFC_ROLEPLAY_DATOS` si esta en el entorno |
| `roleplay/ajustes.py` | `ajustes.json` de cada persona (`juego` elegido a mano, `sin_ia`); leer nunca falla |
| `roleplay/diagnostico.py` | `revisar()`: modo, clave, base, juego, microfonos, una captura de prueba (solo el tamano) |
| `roleplay/models.py` | Dataclasses `PlayerProfile`, `MatchInterviewRecord`, `NoticiaPrensa`, `InstagramPost` + catalogos del quiz |
| `roleplay/database.py` | SQLite. Mapeo GENERICO dataclass <-> fila (`TABLAS`, `_insertar`, `_desde_fila`); `_editar_estado` para leer-modificar-escribir `estado_json` en una transaccion |
| `roleplay/gemini.py` | **Unico punto de llamada a Gemini**: `generar_json(prompt, Esquema, que_hacer, adjunto=(bytes, mime))` sobre `generate_content_with_fallback` |
| `roleplay/servicios/contexto.py` | `ficha_jugador(perfil, backstory=, ganchos=)`: como se describe el jugador en TODOS los prompts |
| `roleplay/servicios/backstory.py` | Backstory + ganchos narrativos |
| `roleplay/servicios/entrevista.py` | Preguntas y evaluacion de respuestas (reaccion + delta de reputacion, tope ±15) |
| `roleplay/servicios/prensa.py` | Hitos deterministas (rachas, goles, rating ultimos 5) + noticias; `calcular_estadisticas_acumuladas` tambien alimenta la carta del Resumen |
| `roleplay/servicios/instagram.py` | Comentarios, likes, seguidores de un post |
| `roleplay/servicios/vision.py` | `MatchStats` + lectura de la captura con Gemini Vision |
| `roleplay/servicios/captura.py` | Captura con dxcam en BGRA + PNG con Qt: **sin OpenCV** (se saco el 2026-10-14) |
| `roleplay/servicios/juego.py` | Encontrar FC 26 (elegido a mano > Steam > EA app > Epic; registro inyectable) y abrirlo con `os.startfile` por su plataforma |
| `roleplay/servicios/accesos.py` | Los dos iconos del escritorio (.url para URLs, .lnk via WScript.Shell por PowerShell) |
| `roleplay/servicios/audio.py` | Voz: `listar_microfonos` (solo la API de audio por defecto), `GrabadorMicrofono` (WAV mono 16 kHz, tope 120 s, `crear_stream` inyectable), `transcribir(wav, pregunta)` |
| `roleplay/partida/formato.py` | Bytes del guardado de FC 26 -> registros (bases de datos de EA, secciones `teams`/`stagadv`/`stndgs`/`compavg`). Valida todo; si algo no calza, `FormatoDesconocido` |
| `roleplay/partida/carrera.py` | `construir(datos) -> Carrera`: equipos, competiciones, partidos, `actuaciones_en(partido)` (quien jugo/marco, de los ultimos 5 partidos de cada jugador), `tabla()` calculada con los resultados, `goleadores()`, `ficha(jugador)`. Los codigos de tablas/campos de FC 26 estan arriba del archivo |
| `roleplay/partida/lector.py` | `carrera_actual()`: el `CmPlr*` mas reciente (o el elegido en Ajustes) de `%LOCALAPPDATA%\EA SPORTS FC 26\settings`, con cache por fecha/tamano. Solo lee. `EAFC_FC26_GUARDADOS` cambia la carpeta |
| `roleplay/servicios/partida_real.py` | Lo que la app hace con la partida: `ultimo_partido()` (stats del ultimo partido; asistencias/tarjetas/figura por diferencia con la lectura anterior, `estado_json.partida`), `contexto_temporada()` (para los prompts), `hechos_destacados()` (hat-trick > goleada > choque de punta, elegidos por codigo), `revisar_prensa_con_partida()`, `resumen_temporada()`, `leer_para_entrevista()` |
| `roleplay/servicios/identificar.py` | La IA pone nombre a jugadores (por su ficha: club, posicion, seleccion, nacimiento) y copas (por sus equipos). Sin seguridad -> nombre vacio. Cache en la tabla `nombre_conocido` |
| `roleplay/ui/vigilante.py` | **Modo en vivo**: `VigilantePartida` mira el guardado cada 5 s (sin abrirlo); si cambio y se asento, lo lee en un hilo. `partido_nuevo` si el club del usuario jugo un partido que no se aviso (`estado_json.partida.avisado`; la primera lectura solo marca); si no, `dia_nuevo` cuando avanzo la fecha del juego (`partida.dia_visto`: jugaron otros). Ajustes `en_vivo.vigilar` / `en_vivo.preguntas_solas` |
| `roleplay/ui/overlay.py` | `SalaFlotante`: panel semitransparente siempre encima (Tool + Frameless + StaysOnTop, `WA_ShowWithoutActivating`: no le quita el foco al juego). Es un ESPEJO de la sala de prensa: lee su estado al recibir `InterviewWindow.cambio` y sus botones llaman a los de la sala (una sola entrevista) |
| `roleplay/ui/atajo.py` | `AtajoGlobal`: Ctrl+Shift+F12 con `RegisterHotKey` (ctypes) + `QAbstractNativeEventFilter`. Ojo: el tipo de evento llega como QByteArray (comparar con `bytes(tipo)`). Si la combinacion esta tomada, `registrar()` da False y la app sigue |
| `roleplay/ui/comun.py` | `ejecutar_en_hilo`, `esc` (escape HTML), `miles`, `fecha_corta`, `con_scroll` (pagina transparente) |
| `roleplay/ui/estilos.py` | Tema oscuro estilo EA FC: colores (unico lugar), `fuente_titulo()`, QSS, paleta forzada |
| `roleplay/ui/componentes.py` | `icono()` (SVG propios coloreados), `titulo_pagina`, `titulo_seccion`, `Tarjeta`, `Mosaico`, `chip`/`chip_tono`, `chip_alternable`, `fila` (None = estirable), `CartaJugador` (carta FUT pintada; nivel por reputacion: bronce <45, plata, oro >=70, elite >=85), `Avatar`, `FondoEstadio`, `agregar_noticia`, `limpiar_layout` |
| `roleplay/servicios/economia.py` | Vida y patrimonio: el sueldo real (`Carrera.sueldo_usuario`, campo `cmGX` de `mPrV`) se acredita con los dias del juego (`acreditar()`, neto 55%; la primera vez, lo cobrado desde el 1 de julio), catalogo sin marcas (casas, autos, relojes, moda, yate, jet) y donaciones; `efecto()` decide seguidores, reputacion, si es noticia y el tono (donar suma; presumir en mala racha resta, mas si es humilde/reservado); `repercusion()` (hilo) escribe la noticia y los comentarios, con respaldo sin IA. Todo en `estado_json.economia` |
| `roleplay/servicios/autos.py` | El concesionario: modelos de marcas REALES (solo el nombre como texto; decision de Simon: la app es entre amigos; nunca logos ni modelos 3D de las marcas), precio base aproximado, opciones con recargo (`precio()`), `describir()` y `Configuracion` (se guarda como dict en el pedido) |
| `roleplay/ui/configurador.py` | `Configurador` (QDialog) y `svg_auto(config)`: una silueta propia por FAMILIA (`SILUETAS`: cuna, 911, super, hiper, gt, sedan, suv, suv_lujo, g), que recuerda la forma del real sin copiarlo ("como GTA": nunca modelos ni assets de GTA ni de las marcas), con sus detalles (tomas de aire, linea en C, rueda de auxilio, aleron si `Modelo.aleron`). **QtSvg no soporta clip-path**: franjas y fibra van como cortes del degradado de la pintura (`_pintura`), y los parantes solo dentro de la ventana. `VistaAuto` dibuja el SVG |
| `roleplay/ui/vida.py` | `PaginaVida`: saldo, sueldo neto, gastos fijos, patrimonio; tienda por categoria, lo que tenes (vender al 70%), filantropia y movimientos. `acreditar_con(carrera)` la llama el menu en cada autoguardado. Los botones se identifican por la propiedad `articulo` (el objectName es el del estilo) |
| `roleplay/servicios/metas.py` | Metas de temporada que se propone el usuario (`estado_json.metas`: goles, goles en liga, asistencias, top N de la liga). `evaluar_metas()` las decide con la partida (contables apenas se llega; el puesto al terminar la liga; las de una temporada pasada fallan) y `texto_para_prompt()` las pone en el contexto de entrevistas y prensa. La prensa devuelve `resultado["metas"]` y la sala lo guarda con `database.actualizar_metas` (que no revive una meta borrada) |
| `roleplay/servicios/mercado.py` | Fichajes reales: `clubes_de_jugadores(carrera)` (hombres, club de hoy) contra la foto anterior de la misma partida (tabla `club_visto`, `database.get/guardar_clubes_vistos`) -> `detectar_traspasos()` (noticia: tu club, media >= 82, o tu liga con media >= 75), `traspaso_del_usuario()` (hito `nuevo_club`). La foto se guarda recien despues de que la IA redacto: si falla, se detectan de nuevo |
| `roleplay/servicios/previa.py` | Conferencia PREVIA al proximo partido: `previa_del_proximo(carrera)` arma los datos reales (tabla de los dos, rachas, ultimo partido del rival, cruces de la temporada, goleador rival; `ya_hecha` con `estado_json.partida.previa`), `generar_previa` / `evaluar_previa` (delta acotado a ±10) y `noticia_de_previa`. NO se guarda como partido (no suma PJ ni goles) |
| `roleplay/servicios/temporada.py` | `vista_temporada(carrera, competicion)`: lo que muestra la pagina Temporada (tabla con el club marcado, goleadores con el jugador del usuario marcado, resultados y proximos del club, la ultima fecha). Liga primero; una competicion ajena cae en la del club |
| `roleplay/ui/temporada.py` | `PaginaTemporada`: chips para elegir competicion, tabla (QGridLayout de QLabel; la fila del club lleva un QFrame resaltado DEBAJO, en la misma celda), goleadores, tus partidos y la ultima fecha. Si se cambia de competicion mientras lee, vuelve a leer al terminar |
| `roleplay/ui/menu.py` | `MainMenuWindow(pagina_inicial)` (lateral con JUGAR FC 26 y AJUSTES + `FondoEstadio`) + `PaginaResumen` (carta, mosaicos, historia, tramas, central de noticias) |
| `roleplay/ui/ajustes.py` | `DialogoClave` (bienvenida: clave de Gemini, la prueba con `models.list` y la guarda), `DialogoAjustes` (clave, juego, iconos, diagnostico), `abrir_juego_o_preguntar` |
| `roleplay/ui/personaje.py` | `CharacterWizard` (ClassicStyle; titulos en rich text con "PASO n/8"; backstory editable o escrito a mano) |
| `roleplay/ui/entrevista.py` | `InterviewWindow` "Sala de prensa": marcador -> preguntas (cada una con boton de voz) -> reaccion -> prensa |
| `roleplay/ui/instagram.py` | `InstagramWindow`: perfil (avatar + mosaicos), nuevo post, resultado, "Tus hinchas" (actividad sin publicar) y feed en tarjetas. `revisar_hinchada()`: una a la vez; si se pide otra mientras corre, se hace al terminar |
| `roleplay/servicios/hinchada.py` | El Instagram que se mueve solo: `eventos_nuevos()` (partidos del usuario y noticias sobre el desde `estado_json.hinchada`; la primera vez solo el ultimo partido), `crecimiento_por_partido/noticia()` (los seguidores los decide el codigo), `comentar_eventos()` (la IA, una consulta; si falla, sin comentarios). Se guarda en la tabla `actividad_instagram` |
| `roleplay/ui/iconos/` | Flechas/check de la QSS (SVG) y `app.ico` (lo genera el script del acceso directo) |
| `scripts/seed_test_matches.py` | Siembra/borra partidos "Rival de prueba N" en el ultimo personaje (base REAL) |
| `scripts/crear_acceso_directo.py` + `scripts/lanzador/Lanzador.cs` | Icono, .exe lanzador (dev) y los dos iconos del escritorio |
| `scripts/empaquetar.py` + `scripts/LEEME_AMIGOS.txt` | Paquete PyInstaller + zip para amigos |
| `tests/` | `ayuda.py` (base temporal, Gemini bloqueado, dialogos mudos) + `test_*.py` |

## Convenciones (respetarlas)

- **Modo en vivo**: ante un partido nuevo, `MainMenuWindow._on_partido_nuevo` avisa en la
  bandeja de Windows (QSystemTrayIcon), marca "Entrevistas ●", la sala lo carga y genera
  las preguntas si esta libre (`InterviewWindow.ocupada()`: nunca pisar una entrevista a
  medias) y corre la prensa. `set_estado_partida` MEZCLA claves (no reemplaza).
  Ante un `dia_nuevo` (autoguardado sin partido del usuario), `_on_dia_nuevo` le pasa la
  partida a la sala y corre la prensa con `solo_hechos=True` (-> `incluir_general=False`: sin
  noticia de ambiente inventada). Toda revision de prensa emite `noticias_publicadas`: el
  menu avisa en la bandeja (solo las automaticas, con la ventana sin foco) y los hinchas
  reaccionan. El kwarg `incluir_general` se pasa SOLO cuando es False (reemplazos de prueba
  de la prensa no lo aceptan).
- **Sala flotante**: toda accion nueva de la sala de prensa que cambie lo que se ve debe
  emitir `self.cambio` (o pasar por `_refrescar_botones`, que lo emite), o el panel no se
  entera. El panel nunca hace logica propia.
- **Hitos reales** (`detectar_hitos_reales`, en `estado_prensa.reales`): goles de la
  temporada (se reinician por temporada, julio a junio), maximo goleador, partidazo,
  liderato ganado/perdido, campeon. Se suman a los hitos del historial de entrevistas.
- **La partida de FC 26 se LEE, nunca se escribe** (y no se toca el juego). Los numeros
  (resultados, goles, tablas, quien es noticia) los decide el codigo; la IA solo pone
  nombres que la partida no trae (con cache) y redacta. Un nombre dudoso va vacio y el
  jugador se describe ("el delantero centro del Arsenal"): nunca inventar.
- **El juego nunca se toca**: ni archivos, ni memoria, ni inyeccion. Se abre por su
  plataforma (`os.startfile` de la URL/acceso) y la app solo lee la pantalla. Por eso no
  lo rompe, las actualizaciones del juego no la rompen y se puede jugar online.
- **Toda llamada a Gemini pasa por `gemini.generar_json`**, que pide
  `response_mime_type="application/json"` + `response_schema=<modelo pydantic>` y
  valida. `que_hacer` es la frase final del error ("apreta X de nuevo"). No
  hardcodear "error 503".
- Fallback: 429 -> siguiente modelo con la misma key; 401/403 -> siguiente key; 5xx ->
  siguiente modelo; otros (400) fallan rapido. Usar `exc.code` (int), **no** `exc.status`.
  El SDK reintenta solo 5xx (3 intentos); el 429 NO se reintenta (era ~1 min de espera
  por modelo con la cuota diaria agotada). Sin key: `FaltaApiKey`, sin "reintenta".
- `google.genai`, `dxcam`, `cv2` y `sounddevice` se importan DENTRO de las funciones
  (arranque 1,9 s -> 0,35 s). `tests/test_ui.py::TestArranque` falla si alguien los
  vuelve a importar arriba. Los microfonos se listan recien al mostrar preguntas.
- **Toda llamada a la API desde la UI usa `ui.comun.ejecutar_en_hilo(func, *args,
  al_completar=metodo, al_fallar=metodo)`**. Nada de clases QThread nuevas ni de
  guardar el hilo en un atributo: el registro `_TareasVivas` lo mantiene vivo hasta
  que termina. Pasar METODOS de la ventana, no lambdas (PySide desconecta los metodos
  si la ventana se destruye).
- Lo que se manda a la IA y vuelve despues se guarda contra el jugador/datos de ESE
  momento (ver `_evaluando`, `_prensa_player_id`, `_publicando`), no contra
  `self.perfil` ni el formulario actual.
- Botones de la entrevista: solo `_refrescar_botones()` decide cuales estan activos
  (incluye grabando/transcribiendo: mientras hay voz en curso no se regenera ni se envia).
- Todo texto de la IA o del usuario que va a un QLabel con formato pasa por `esc()`;
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
- Lo que genera la IA queda **editable** antes de guardarse (backstory, ganchos, stats,
  transcripciones).
- Estado de modulos nuevos va en `player_profile.estado_json` (ej: `reputacion_actual`,
  `historial_reputacion`, `prensa`, `seguidores_instagram`) para no migrar el esquema.
  Columnas nuevas reales: agregarlas al `SCHEMA` **y** a `COLUMNAS_AGREGADAS`
  (la DB del usuario ya existe y tiene datos). Un campo nuevo en un dataclass necesita
  su columna: el mapeo generico falla fuerte si falta.
- Las paginas del menu exponen `actualizar()`, que recarga el perfil; el menu lo llama al navegar.
- Strings de UI en espanol (voseo/chileno informal), sin tildes en el codigo.
- Los prompts piden no inventar nombres de personas/jugadores reales.

## Testing

`.venv\Scripts\python.exe -m unittest discover -s tests` (232 pruebas, ~16 s). `tests/ayuda.py`:
- Fija `EAFC_FC26_GUARDADOS` a una carpeta vacia: las pruebas no leen la partida real.
  `tests/fabrica_partida.py` arma un guardado FALSO con el mismo formato (para todo lo de
  `roleplay/partida`). `TestPartidaRealDelPC` lee la partida real si existe (solo lectura,
  exige que >90% de los marcadores cuadren con los goles de los jugadores); si no, se salta.
- Fija `EAFC_ROLEPLAY_DATOS` a una carpeta temporal ANTES de importar `roleplay`: ni las
  pruebas ni sus subprocesos escriben en la carpeta del proyecto.
- `PruebaConBase`: base temporal por prueba (`config.DB_PATH` parcheado).
- `PruebaDeInterfaz`: + QApplication offscreen + `QMessageBox.information/warning` mudos (en `self.avisos`).
- Gemini queda bloqueado: si algo llama a `_cliente` de verdad, la prueba falla.
  Mockear `generar_json` en el modulo del servicio (ej. `roleplay.servicios.prensa.generar_json`).
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
  `"dist\EAFC Roleplay\EAFC Roleplay.exe" --diagnostico` (sale 1 solo por falta de clave).
- No probado automaticamente: microfono real, respuestas reales de Gemini y abrir el juego
  de verdad (`os.startfile` va mockeado; no lanzar FC 26 en el PC de Simon sin preguntar).

## Gotchas conocidos

- Windows en modo oscuro deja labels invisibles si no se fuerza la paleta (por eso `estilos.py`).
- `.env` en Windows suele quedar como `.env.txt`; crearlo desde VS Code.
- Paths en PowerShell: `.venv\Scripts\python.exe`, no `/c:/...`.
- Tier gratis de Gemini: 503 por demanda y 429 por cuota son frecuentes; el fallback lo maneja.
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
2. Entrevistas post-partido (captura + Gemini Vision, o stats a mano; respuestas escritas
   o por voz; reaccion + reputacion evolutiva)
3. Prensa: hitos del jugador + noticias generales del mundo
4. Instagram: posts, comentarios, likes, seguidores
5. Interfaz estilo EA FC (tema oscuro, carta FUT por nivel de reputacion, scroll por pagina)
6. Lanzador .exe + icono + acceso directo; pruebas automaticas (unittest)

Hecho tambien: iconos "EA FC 26" / "EA FC 26 + Roleplay", boton JUGAR, Ajustes con
diagnostico, el paquete para amigos (cada uno con su clave y sus datos en APPDATA) y
la lectura de la partida de FC 26 (ver arriba).

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
  el club, la prensa escribe sobre hechos reales con nombres reconocidos. Formato y
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
- Reputacion por club + eventos de decision (quedarse/irse tras una polemica, clubes que no te quieren por tu historial)
- ~~Economia / lifestyle~~ y ~~filantropia~~: hechos (ver arriba)
- Eventos inesperados (lesiones, accidentes, enfermedades; buenos y malos)
- Vida sentimental: novia real vs posibilidad de relacion con una famosa, con tramas

## Como trabajar con Simon

- Respuestas directas y practicas, en espanol.
- A veces implementa partes el mismo: antes de reescribir algo, revisar lo que ya hizo y
  preguntar si hace falta. Si pide revision, revisar y corregir bugs reales (con prueba que los demuestre).
- Entregar cambios probados; avisar explicitamente lo que no se pudo probar (dxcam, microfono real).
