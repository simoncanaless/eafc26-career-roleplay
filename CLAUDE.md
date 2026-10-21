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
- **Estado al 2026-10-20** (490 pruebas en verde, todo en GitHub):
  00. Ecosistema de Simon (2026-10-20): conferencias con 8 tematicas y periodistas reales, parejas del catalogo
     con DM y romance secreto, seguidores por tier y exposicion, patrocinios, tienda de lujo, hiperautos,
     marketplace de nicho, comentarios de colegas/famosas y feed global (ver `ecosistema.py`). Los datos estan
     en `files/roleplay/datos/` (copiados de `Desktop/roleplay/datos/`, donde los dejaron sus scripts).
     Fotos de los autos ARREGLADAS el 2026-10-20: el script de Simon `Desktop\scripts\descargar_imagenes_google.py`
     (la version vieja, que tomaba lo primero de Bing, quedo en `..._anterior.py`) ahora baja SOLO de Wikimedia
     Commons, verifica que el nombre del archivo nombre al modelo (codigos, version, anio +-2) y fija a mano
     (`FOTOS_ELEGIDAS`) las que la busqueda no resuelve; guarda `imagen_credito` (autor y licencia), que el
     marketplace muestra. Las 95 revisadas a la vista. Respaldo previo en `Desktop
oleplay
espaldo-fotos-2026-10-20`.
     Si se regeneran, copiar `autos_marketplace.json` e `img_autos/` a `files
oleplay\datos\`.
  0. Nombres de jugadores: HECHO el 2026-10-16 (catalogo de EA local + diccionario de ids de nombre;
     ver `identificar.py`). En un PC nuevo, correr `scripts\nombres_faltantes.py --catalogo-ea` (sin el
     catalogo, casi todos salen descritos y `empaquetar.py` se niega a armar el paquete).
  1. Noticias inventadas: SACADAS el 2026-10-16 (la prensa solo escribe sobre lo real).
  2. Pilar 3 (tienda universal): HECHO el 2026-10-20 (`ui/tienda.py`, boton en Vida); falta solo "Presumir en
     Instagram" con la foto de la compra (InstagramPost.foto). No probado con el navegador real abierto.
  3. Pilar 4 (overlay bimodal): HECHO el 2026-10-16; el overlay completo probado por Simon encima del juego el 2026-10-20.
  4. IA hibrida (Groq -> Gemini -> motor local): HECHA el 2026-10-16; probada con la clave real de
     Simon el 2026-10-16 (Groq gpt-oss-120b, ~0,45 s). Su `.env` viejo tiene GEMINI_API_KEY: queda de respaldo.
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
.venv\Scripts\python.exe scripts\partida_de_prueba.py [--reiniciar] [--reputacion 95] [--seguidores N]   # partida imaginaria (files/prueba, .gitignore): personaje soltero + partida falsa, para probar las parejas sin tocar la real; sin espera entre DMs (EAFC_DM_SIN_ESPERA=1). Queda registrada en "Tus carreras" (id `prueba`): tambien se abre desde Ajustes
```

**Iconos del escritorio** (`servicios/accesos.py`, tambien desde Ajustes en la app):
"EA FC 26.url" (`steam://rungameid/3405690`, el juego normal) y "EA FC 26 + Roleplay.lnk"
(la app con `--jugar`: abre el MISMO juego por su plataforma y la app). El FC 26 de Simon
esta en Steam, biblioteca `F:\SteamLibrary` (EA app instalada, la usa Steam).

**Paquete para amigos**: `dist\EAFC Roleplay (amigos).zip` (~215 MB, casi todo Chromium; rearmado el 2026-10-20 con el overlay arreglado y el mando -SDL2.dll via `--collect-all sdl2dll`-, LEEME al dia y probado como amigo nuevo con `--diagnostico`, que ve el DualSense; el script controla que no vayan `carreras.json` ni tus datos y que vayan las fotos de los autos y `qtbase_es.qm`) con
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
| `roleplay/carreras.py` | **Perfiles de carrera** (2026-10-20, pedido de Simon): mas de una carrera (la principal, la de prueba, otro modo carrera de FC 26), cada una con su carpeta de datos (base, ajustes con su `partida`, fotos). La principal es la carpeta de siempre; las demas, `<principal>/carreras/<id>/`; la lista y la activa en `<principal>/carreras.json` (`.gitignore`). `app.py` llama a `preparar_entorno()` ANTES de importar `config` (pone `EAFC_ROLEPLAY_DATOS` y, si la carrera los trae, `EAFC_FC26_GUARDADOS` / `EAFC_DM_SIN_ESPERA`); si `EAFC_ROLEPLAY_DATOS` ya viene en el entorno no toca nada. `crear()` copia las claves de IA de la principal; `activar()` + `ui.ajustes.reiniciar_app()` (relanza con `entorno_para_reiniciar()`, sin esas variables) = cambiar de carrera. `actual()`: la de este proceso (el titulo de la ventana la muestra). NO importa `roleplay.config`. `EAFC_ROLEPLAY_BASE` cambia la principal (las pruebas: una temporal) |
| `roleplay/ajustes.py` | `ajustes.json` de cada persona (`juego` elegido a mano, `en_vivo`...); leer nunca falla |
| `roleplay/diagnostico.py` | `revisar()`: modo, motor narrativo (cuantos archivos en `roleplay/datos`), IA hibrida (`ia.estado()`: cuantas claves, sin mostrarlas), base, juego, microfonos, una captura de prueba (solo el tamano), navegador |
| `roleplay/datos/` | **Los datos del motor narrativo** (JSON, sin tildes; los emojis si van): `corpus_entrevista.json` (preguntas de los 3 periodistas, reacciones, previa), `corpus_prensa.json` (titulares/cuerpos por hito, cruces `x_*`, mundo: solo hechos reales), `corpus_redes.json` (comentarios por tipo y tono, autores, posts sugeridos por personalidad), `corpus_vida.json` (backstory y ganchos), `lexico.json` (5 ejes con pesos por palabra/frase, negaciones, promesas), `jugadores_fc26.json` / `competiciones_fc26.json` (nombres por id de EA CON fecha de nacimiento: si la de la partida no calza, es otra persona y queda sin nombre; se suman con `scripts/nombres_faltantes.py --agregar`). Claves que empiezan con `_` son comentarios |
| `roleplay/servicios/ia.py` | **IA hibrida opcional** (solo `urllib`): `pedir_json(sistema, usuario, esquema, timeout=6)` -> dict o None, NUNCA lanza. Cascada: Groq `openai/gpt-oss-120b` (con `reasoning_effort: low`, ~0,45 s) -> `gpt-oss-20b` -> `qwen/qwen3.8-27b` (429/5xx/404 -> el siguiente; 401/403 -> la siguiente clave; si los TRES dan 404, `modelos_de_groq()` pide `/models` y prueba los de chat que haya: el 2026-10-16 Groq ya no tenia los Llama 3.x) -> Gemini REST `gemini-2.5-flash` -> `-flash-lite` -> None (toda la cascada a lo sumo 2x timeout). `REGLAS` en cada pedido: no inventar datos ni nombres reales. Apagada con `sin_ia` en ajustes o `EAFC_SIN_IA=1` (lo pone `tests/ayuda.py`). `probar()` (boton de Ajustes), `estado()` (diagnostico), y piezas: `texto` (limpia y acota), `entero` (acota), `ficha`, `describir_cruces`, `comentarios_validos`, `cita_literal` (la cita solo vale si son palabras textuales del jugador). Quien la usa: `entrevista.preguntas_con_ia` / `reaccion_con_ia` (tambien la previa), `instagram._comentarios_con_ia`, `hinchada._comentarios_con_ia` (una llamada para todos los eventos; los que falten, del corpus) y `prensa._nota_con_ia`. Siempre DESPUES de calcular lo local, que queda de respaldo |
| `roleplay/servicios/memoria.py` | **Roleplay vivo** (2026-10-20, Simon: "que se sienta vivo, como roleplay, no como un guion"): `cronica(player_id)` (~1.700 caracteres, tope 2.400) junta quien es (personalidad, motivacion, backstory), como viene (reputacion y sus ultimos cambios, ultimos 3 partidos), lo que DIJO en sus ultimas conferencias (`anotar_dichos`, que llaman `evaluar_respuestas` y `evaluar_previa`: `estado_json.conferencias.dichos`, ultimos 6; `armar_conferencia` los conserva), su vida (pareja, hijos, momentos, carino de la hinchada, eventos, marcas, ofertas), las tramas de conferencias anteriores y los ultimos titulares. `ia.pedir_json(..., jugador=id)` la pone adelante del pedido y suma la consigna `ia.VOZ` (gente real con opinion y memoria, sin plantillas ni frases hechas, la memoria es contexto de ANTES y toda opinion coherente con ella). **Guardia de hechos** (`ia._sin_numeros_inventados`): todo texto de la respuesta con un numero que no esta en el pedido vuelve vacio y ese campo cae al motor local (las preguntas, una por una). La usan: las preguntas (los periodistas retoman lo que dijo; si le hablan al periodista por su nombre, se corrige), la reaccion (post y previa; `ajenos`: si la nota trae al goleador del rival que el no nombro, se descarta), la nota de la entrevista, `prensa.reescribir_con_ia` (TODAS las noticias de una revision en una llamada, y la de cada `eventos.contar`: vida, pareja, compras, marcas, hinchada; la de la entrevista no se toca), `contratos.frase_con_ia` (la directiva en la mesa, en un hilo: llega despues de la del corpus), `instagram.sugerir_post` y los comentarios de Instagram y de la hinchada. NO la usa el feed global (las paginas son cuentas reales de los datos de Simon: la IA no escribe en la voz de personas reales) |
| `roleplay/servicios/ecosistema.py` | **Los datos de Simon** (sus scripts, 2026-10-19): `famosas_ig.json` (5.360 celebridades: nombre, usuario_ig, oficio, categoria, exigencia), `ecosistema_ig.json` (15 `paginas_futbol` con `tipo` viral/mercado/medio/polemica/farandula, 259 `periodistas` con `estilo` tactico/vestuario/mercado/polemico, 594 `futbolistas_ig` con `fama_minima_para_comentar`) y `autos_marketplace.json` (95 `autos_nicho` + fotos en `img_autos/`). **Son de Simon y su responsabilidad**: la app solo los LEE (nunca los escribe ni modifica), van en `.gitignore` (personas reales y fotos: no al repo publico) y SI en el paquete de los amigos. Claude no escribe contenido sobre personas reales: arma el funcionamiento y los textos genericos del corpus. Sin los archivos todo anda (listas vacias); `EAFC_ECOSISTEMA` cambia la carpeta (las pruebas: una vacia). Ademas: `tier_club(carrera, club)` (tier MEDIATICO: `TIER_1` / `TIER_2` por nombre normalizado -Real Madrid, Man Utd, Barca, City, Bayern, PSG, Liverpool, Arsenal, Chelsea, Juventus son 1; PSV, Benfica, Dortmund, Milan (Milano FC), Atletico, Inter (Lombardia FC), Napoli, Porto, Ajax... son 2-; el resto por la media de los 16 mejores del plantel: >= 74 tier 2, si no 3; memo en `Carrera.memo`), `fama_jugador()` / `calcular_fama_jugador(perfil o id, carrera)` (Player Power Index 0-100: reputacion x 0,45 + base del tier 35/20/8 + goles y asistencias de la temporada + premios y titulos de la vitrina) |
| `roleplay/servicios/feed.py` | Feed global: con cada revision de la hinchada, las paginas publican sobre los eventos nuevos (`_tipo`: partido con gol -> viral, romance -> farandula, cita -> medio/polemica, lujo -> viral) y, con fama >= 60, a veces un rumor de un gigante (`feed_rumor`, "HERE WE GO?"). Corpus `feed_*` en `corpus_redes.json`. Tope 30 en `estado_json.hinchada.feed` |
| `roleplay/servicios/patrocinios.py` | Contratos con marcas (nombres reales en texto, como los autos): `MARCAS` (**56 desde el 2026-10-20**, todo lo que rodea al futbol: botines -Nike, Adidas, Puma, New Balance, Mizuno, Under Armour, Joma, Umbro-, bebidas, tecnologia, electrodomesticos -LG, Philips, Hisense, TCL, Midea-, videojuegos -EA SPORTS FC, PlayStation-, auriculares, cuidado personal, relojes, moda, autos, aerolineas, bancos y tarjetas, comida; un contrato por rubro -EXCLUSIVIDAD: Pepsi y Coca-Cola, Nike y Adidas no van juntas; la tarjeta lo dice-, maximo 8; `_rubro` traduce los rubros viejos. Sin genericas desde la segunda pasada: "local" es Kelme y "bebida" es Zuko -`nombre_de` renombra los contratos guardados-, y hay marcas chicas para empezar: Penalty, Lotto, Aquarius, Entel, Claro, PedidosYa, Rappi, Myprotein, DXRacer, Smart Fit...; rubros nuevos telefonia, delivery, suplementos, sillas gamer, gimnasios, musica. **Varias ofertas a la vez** (`economia.patrocinios.ofertas`, hasta `MAXIMO_OFERTAS` 3, de rubros distintos; `pendientes()` lee tambien la `oferta` unica de antes; `responder(..., marca)`)). **Promos**: al firmar y cada 30 dias del juego cada marca pide algo (`PROMOS`: post en Instagram, sesion de fotos, evento, comercial; `PROMOS_POR_RUBRO` lo concreta, ej. la promo de LG en una tienda de electrodomesticos), con 21 dias de plazo: `cumplir()` paga una semana del contrato de bono (el post se publica de verdad en su Instagram con `instagram.post_promo`, corpus `post_promo_*` con #publi); si vence, falta (noticia mixta) y a la segunda la marca se va con multa. `buscar()`: boton "Buscar marcas" (el representante, una vez por semana del juego; sin espera en la partida de prueba; si no hay nivel, dice que pide la proxima) con seguidores/reputacion minimos y pago semanal; `revisar()` (una oferta por semana como mucho, de la mejor marca de un rubro que no tenga; vencimientos; rescinde si la reputacion cae 12 bajo el minimo o con un escandalo -evento negativo de los ultimos 14 dias, `hubo_escandalo`- y ahi multa 2 semanas), `responder()`, `ingreso_semanal()`. Estado en `economia.patrocinios` |
| `roleplay/servicios/contratos.py` + `roleplay/ui/contrato.py` | **Primas del contrato** (2026-10-20, pedido de Simon): el SUELDO base es el del juego (se negocia en FC 26); con la directiva se negocia lo demas, como en los contratos filtrados: `CLAUSULAS` firma (en cuotas, una por temporada; 10% para el representante), gol, meta de goles (`META_GOLES` por linea: 20 ataque, 10 medio, 5 defensa, 1 arco), jugador del mes, titulo de liga, Balon de Oro, fidelidad (por temporada completa) e imagen (% del sueldo por semana, tope 20; lo suma `economia.acreditar`). Todo en semanas de sueldo. Calibrado con Football Leaks y la prensa (Martial: 7,2 M por cada 25 goles; Balon de Oro 1-4 M de Ronaldo/Di Maria; Kroos: 50% de imagen para el club). `abrir()`: techo ESCONDIDO por clausula (tier `FACTOR_TIER` x `palanca` por fama, idolo de la hinchada y ritmo de goles, +-10%) y primera oferta al 55-75%; `contraofertar()`: todo bajo el techo -> acepta; hasta 25% de `exceso` -> sube hasta su techo y -1 de paciencia; mas -> ofendida, -2; sin paciencia (3, 4 si es idolo) -> rota (noticia, carino -2, `negociacion_rota` hasta la temporada que viene). `consejo()`: el representante (margen/justo/pasado). Cerrar sin firmar guarda `economia.negociacion` tal cual. `firmar()` (1-5 temporadas), `cobrar()` en cada autoguardado (`PaginaVida._cobrar_primas`: goles de la partida desde que firmo, meta, premios de la vitrina, fidelidad y cuota al cambiar de temporada; si cambia de club, el contrato termina), `balon_de_oro()` lo anota el usuario (la partida no lo guarda; una vez por temporada; noticia +6 de reputacion). `puede_negociar`: sin contrato con ese club, o mejora si la fama subio 10 desde que firmo (una por temporada). Tarjeta "Tu contrato: primas" en Vida. Textos de la directiva y el representante en `corpus_vida.json` (`neg_*`, `rep_*`) |
| `roleplay/servicios/premios.py` | **Premios con su nombre y la gala** (2026-10-20, pedido de Simon). `nombre_premio(tipo, liga)`: cada liga con sus premios (`POR_LIGA`: Jugador del Mes de la Premier, Trofeo Pichichi, Capocannoniere, Scudetto, Torjaegerkanone, Bola de Prata...; si no esta, generico). La vitrina guarda `tipo` (jugador_del_mes, campeon, maximo_goleador o el id del premio global) y `premio` con ese nombre (`partida_real.nombre_en_vitrina`). `gala(carrera)`: Balon de Oro, Trofeo Kopa y Trofeo Gerd Muller (France Football), The Best (FIFA), Golden Boy (Tuttosport) y Bota de Oro europea (ESM), decididos por el CODIGO con los numeros reales de la temporada de todos los jugadores de la partida (`Candidato.puntaje`: goles + 0,6 asist. por el peso de la liga, nota, titulos de su club -`campeones()`: liga terminada 12, final continental 15, copa 5- y media; minimo 15 partidos; Kopa/Golden Boy sub-21; Bota de Oro con el coeficiente ESM). `partida_real.gala_de_la_temporada` la corre una vez por temporada cuando termina la liga del usuario (`estado_prensa.gala`): si gana, hito `premio_global` (vitrina, +6 de reputacion cada uno, la prima del Balon de Oro se cobra sola); podio del Balon de Oro / The Best, `candidato_premio`; si el Balon de Oro es de otro, noticia del mundo `gala`. **La carrera entera** (`Carrera.etapas`, tablas `YMgA`/`NgwF`/`cPet`, ver `docs/partida-fc26.md`; `cPet` guarda uno MENOS de cada premio -`AJUSTE_PREMIOS`-, verificado club por club con las pantallas del juego: Palermo 22/8, Man Utd 16/6; futbolista del partido = `OcFS`, 34 y 29): tarjeta "Tu carrera en FC 26" en el Resumen (`partida_real.carrera_completa`) y **el jugador del mes del usuario lo da EL JUEGO** (`premios_del_juego`: si el contador de `cPet` de su club sube; el calculado por la app queda solo para los demas) |
| `roleplay/servicios/ofertas.py` | **Ofertas de otros clubes** (2026-10-20, Simon: "escuchar ofertas no es querer irse"). En las ventanas de pases (julio, agosto, enero), una revision por semana del juego (`probabilidad(fama)`, hasta 0,65; maximo 3 abiertas): `interesados()` (clubes cuyo plantel -`ecosistema.medias_de_plantel`, promedio de los 16 mejores- esta entre tu media - 12 y tu media + fama/10, de tu tier o uno abajo; los mejores pesan mas). La oferta: sueldo (`sueldo_de_mercado`: 150.000 por semana en un tier 1 a media 80, x1,1 por punto, x0,4 tier 2, x0,12 tier 3; siempre mas que el actual), temporadas y primas cerca del techo de ese club; vence en 14 dias. `responder`: rechazar; "negociar" (`palanca_extra` 0,25/0,15/0,08 segun el tier: la proxima mesa con tu club arranca con mas palanca, `contratos.abrir(extra=)`); aceptar (descarta las otras; el traspaso lo hace EL JUEGO: si en 60 dias la partida lo muestra en ese club, `cumplida` y las primas de la oferta se firman solas; si no, `caida`). Noticia si ofrece un tier 1-2. Tarjeta "Ofertas de otros clubes" en Vida. `EAFC_SIN_OFERTAS=1` en las pruebas (la partida de prueba cae en enero). La decision "tentado" de `clubes.py`: "Escuchar la oferta, sin compromiso" ya no baja el carino. **La negociacion de primas se ve en PLATA** (`contratos.monto`/`rotulo`: "£80.000 por gol"; por dentro siguen en semanas de sueldo; el dialogo pide plata y la imagen en %) |
| `roleplay/servicios/marketplace.py` | Usados y autos de culto: `ofertas(player_id, hoy)` rota 8-12 por semana del juego (semilla jugador+semana) con km, estado ("Importado de Japon" solo los JDM) y precio por rareza; compra al instante (`articulo`, `extra_de`: posesion `nicho:<id>`); `valor_actual()` se valoriza por anio segun la rareza y `valor_de_reventa()` descuenta 5% de comision. La foto se guarda por NOMBRE de archivo y se resuelve con `ruta_imagen()`; `credito` (autor y licencia de Commons) se muestra debajo |
| `roleplay/servicios/narrador.py` | **Motor de gramaticas**: `Narrador(*corpus, usados=, dado=, ricas=)`: `decir(simbolo, **datos)` (texto nuevo, anotado), `elegir()` (pieza sin anotar), `puede()`, `tiene()`. Alternativas con `{variable}` (solo entran si estan todos los datos) y `#simbolo#` (recursivo). Anti-repeticion: por simbolo los ultimos bloques (min(40, n-1): siempre queda uno libre) + huellas de los ultimos 40 textos; si sale uno reciente se rearma sorteando entre TODAS las piezas (con la rueda, dos piezas iguales rotan en fila). `narrador(player_id, *corpus)` (context manager) carga/guarda `estado_json.narrador_usados`; sin perfil (o borrado), sin memoria. `unir()`/`limpiar()` (espacios, mayuscula tras punto; un @usuario al principio no se toca) |
| `roleplay/servicios/lexico.py` | **Evaluador lexico**: `puntuar(texto)` (5 ejes: humildad_equipo, amor_hinchada, ego_confianza, excusa_polemica, ambicion_foco; tildes y mayusculas no importan; una negacion en las 2 palabras previas invierte el peso), `leer(respuestas) -> Lectura` (eje dominante o `neutro` bajo 1.5, intensidad, `cita` = la oracion mas jugosa recortada a 150, `promesa`, palabras) |
| `roleplay/servicios/cruce.py` | **Estado cruzado**: `cruces(player_id, rival=, rating=, carrera=)` -> lista de `Cruce(tipo, peso, datos)` del mas jugoso al menos: compra cara (>= 150.000, ultimos 45 dias; con rating < 6.2 `compra_mal` con modelo y precio), pareja real/famosa/rumor/crisis, meta cerca (con la partida, lo que lleva HOY) o complicada, ex club (traidor/idolo/mala salida), hinchada en contra/idolo, evento reciente (21 dias). Solo lee. Importa `metas` adentro de la funcion (ciclo metas -> partida_real -> prensa -> cruce) |
| `roleplay/models.py` | Dataclasses `PlayerProfile`, `MatchInterviewRecord`, `NoticiaPrensa`, `InstagramPost` + catalogos del quiz |
| `roleplay/database.py` | SQLite. Mapeo GENERICO dataclass <-> fila (`TABLAS`, `_insertar`, `_desde_fila`); `_editar_estado` para leer-modificar-escribir `estado_json` en una transaccion |
| `roleplay/servicios/backstory.py` | `generar_backstory(perfil, dado=)`: 3 parrafos (origen, personalidad+motivacion, vida personal+anecdota+cierre) con `ricas=True` (prefiere las alternativas que usan mas datos del quiz) + 3-4 ganchos distintos |
| `roleplay/servicios/entrevista.py` | **Tres periodistas** (`PERIODISTAS`): Ignacio Ferrada (Pizarra Tactica: numeros, tabla, racha), Valentina Aros (Radio Tribuna: vestuario, hinchada, metas, ex club) y Rocco Salinas (El Picante: compras, pareja, eventos, contradicciones). `generar_entrevista(perfil, stats)`: cada uno elige la pregunta de mas prioridad que el corpus pueda escribir; `_memoria()` mira las ultimas 10 entrevistas (sequia rota >= 3, racha, caida de nota, mismo rival antes, contradiccion: ego la fecha pasada y hoy derrota) y `_tabla()` la tabla antes/despues del partido. `evaluar_respuestas()`: `lexico.leer` -> delta (BASE por eje x resultado, intensidad, personalidad, rating, respuestas secas, promesa; tope ±15), `delta_carino` (lo aplica la sala a `clubes.sumar_carino`), cita y gancho si prometio algo. `reaccionar()` = apertura + nucleo + cruce + cierre **Desde el 2026-10-20 sin esquema fijo**: `TEMAS` (8: vestuario, mercado, tactica, racha, arbitraje, vida_privada, contratos, hinchada); `temas_comunes()` + los del partido arman candidatos por tema y pesos segun el contexto (roja, derrota, mercado del club, rumores, patrocinio...); `_sortear_temas()`: los de prioridad >= `OBLIGATORIO_DESDE` (7) van si o si, el resto por sorteo ponderado, y siempre una de `DEL_PARTIDO` (tactica/racha). `periodista_para()`: un periodista REAL de `ecosistema.periodistas()` de un estilo del tema (`ESTILO_DE_TEMA`: el "emocional" pregunta por la hinchada y la vida privada; sin datos, los 3 de siempre), tres distintos; los reales firman "Nombre @usuario (Medio): ..." (`preguntas_con_ia` le saca el @ al comparar). `armar_conferencia()` la usan la post y la previa; la IA recibe el tema de cada pregunta. Textos `tema_*` en el corpus. **Con los datos de verdad** (2026-10-20, Simon: "con el Stoke tan cerca" siendo el Stoke ultimo y el primero): en la previa, `previa.como_llegan` elige la pregunta de la tabla por la diferencia REAL (`pv_tac_tabla` solo si estan a 3 puestos o 6 puntos; si no `pv_tac_tabla_favorito` / `pv_tac_tabla_abajo` con `{diferencia}`; el ultimo dice "(ultimo)"); `temas_comunes(previa=True)` cambia las preguntas que solo valen despues del partido (`SOLO_DESPUES_DEL_PARTIDO`: pareja mirando, dedicatoria, palco, compras "hoy jugaste") por sus `pv_pic_*`; la marca se nombra con `patrocinios.nombre_de` y "te vimos en la campana" (`tema_patrocinio_campanas`) solo si ya cumplio una promo; `SISTEMA_PREGUNTAS` le prohibe a la IA inventar numeros o preguntar por el partido en la previa. **Variedad** (2026-10-20, pedido de Simon; `scripts/medir_variedad.py` simula N conferencias seguidas: de 55 preguntas distintas en 120 se paso a 85, sin repetir ninguna en las ultimas 3): (1) **piezas combinables** en el corpus: los simbolos de relleno suman `#a_x# #ctx_y# #q_y#` (`q_tactica`, `q_vestuario`, `q_hinchada`, `q_arbitraje`, `q_vida`, `q_contratos`, `q_mercado`, `q_victoria/derrota/empate` con su `ctx_*`, `q_previa_*`) y 7 aperturas mas por estilo; (2) **temas con los datos reales** (`temas_de_los_datos`: goles de la temporada y de toda la carrera -`Carrera.etapas`-, asistencias, racha sin perder del club, el ultimo premio de la vitrina, una oferta de un club tier 1-2 de los ultimos 30 dias, primas firmadas o la negociacion rota, un hijo o la boda de los ultimos 90 dias, los seguidores); (3) **sorteo con memoria** (`database.get/set_memoria_conferencias`, `estado_json.conferencias`: ultimos 12 simbolos, temas de las ultimas 4 conferencias y 15 textos): dentro de un tema se sortea por prioridad (`PENALIDAD_RECIENTE` 0,1 a lo preguntado hace poco), los temas de la conferencia anterior pesan 0,4; lo obligatorio (>= 7) sigue yendo si o si, y la pregunta del partido (`la_mejor`) es siempre la de mas datos que no se hizo hace poco; (4) **repreguntas** (`repregunta`: la cita o la promesa de su conferencia anterior segun el eje del lexico -`TEMA_DE_EJE`-, simbolos `rep_*`); (5) **la IA sin repetir**: `preguntas_con_ia(..., recientes)` le pasa las ultimas 15 preguntas para que no las repita ni las parafrasee. **Fichajes de SU linea** (2026-10-20, Simon: le preguntaban por un lateral siendo 9): el mercado guarda `jugador`, `llega` y `posicion` de cada traspaso; `contexto_de_club(perfil, carrera)` solo toma uno de la misma `LINEA` (arco/defensa/medio/ataque) que `posicion_del_usuario`; llega -> `tema_mercado_llega` (competencia o acomodarse; `puesto_compartido` si es su mismo puesto), se va -> `tema_mercado_sale`. Sin posicion conocida (traspasos viejos), no se pregunta por fichajes. La IA recibe su posicion y tiene prohibido atribuirle otra |
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
| `roleplay/servicios/identificar.py` | Nombres por id de EA, en orden: `jugadores_fc26.json` (a mano) > `catalogo_ea.json` (el catalogo oficial de ratings de EA, ~21.500 jugadores con `pila`/`apellido`/`comun`/`nacimiento`; **SOLO local**: `.gitignore`, lo baja `nombres_faltantes.py --catalogo-ea`, va en el paquete; `EAFC_CATALOGO_EA` cambia la ruta) > **diccionario de ids de nombre** (`diccionario_de_nombres`: la partida trae para cada jugador los ids de nombre/apellido/comun de la tabla `playernames` del juego, pero NO el texto; el texto se aprende de los jugadores de la partida que estan en el catalogo con el nacimiento que calza, y un id con dos textos se descarta; asi se nombra a regens y juveniles: comun, o nombre + apellido, o solo el apellido). En la base a mano y el catalogo, si el nacimiento no calza con la ficha, nombre vacio (otra persona). `partida_real.diccionario_de(carrera)` lo arma una vez por lectura (`Carrera.memo`). Copas: `competiciones_fc26.json`. **Nunca inventar nombres** |
| `roleplay/ui/vigilante.py` | **Modo en vivo**: `VigilantePartida` mira el guardado cada 5 s (sin abrirlo); si cambio y se asento, lo lee en un hilo. `partido_nuevo` si el club del usuario jugo un partido que no se aviso (`estado_json.partida.avisado`; la primera lectura solo marca); si no, `dia_nuevo` cuando avanzo la fecha del juego (`partida.dia_visto`: jugaron otros). Ajustes `en_vivo.vigilar` / `en_vivo.preguntas_solas` |
| `roleplay/ui/overlay.py` | `SalaFlotante`: panel semitransparente siempre encima (Tool + Frameless + StaysOnTop, `WA_ShowWithoutActivating`: no le quita el foco al juego). Es un ESPEJO de la sala de prensa: lee su estado al recibir `InterviewWindow.cambio` y sus botones llaman a los de la sala (una sola entrevista). **Bimodal**: HUD (`mostrar()`, `WindowTransparentForInput`: mouse y teclado pasan al juego; `avisar(titulo, texto)` muestra un aviso 9 s y, si estaba escondida, aparece compacta (`cuerpo` oculto) y se esconde sola) e interactivo (`atajo_presionado()` / `modo_interactivo()`: guarda la ventana del frente (`GetForegroundWindow`), toma el foco; `modo_hud()` o "Volver al juego" le devuelve el foco con `SetForegroundWindow`). Cambiar el flag esconde la ventana: `_aplicar_modo` la vuelve a mostrar. Sin el atajo (`click_a_traves=False`) nunca deja pasar los clicks. Las llamadas a Windows solo con la plataforma "windows" (no en offscreen). El menu manda avisos de partido nuevo, dia nuevo (si esta a la vista), auto entregado, evento inesperado y prensa (`_avisar_encima`: con "flotante" prendido y la app sin foco) |
| `roleplay/ui/overlay_completo.py` | **Overlay completo, como Overwolf** (2026-10-20, pedido de Simon): `OverlayCompleto(ventana)` convierte la ventana principal en una capa sin bordes, siempre encima y a pantalla completa EN EL MONITOR DEL JUEGO (`pantalla_de_la_ventana`: MonitorFromWindow + `szDevice` = `QScreen.name()`), con `setWindowOpacity` (`ajustes.overlay.opacidad`, 0,7-1, por defecto 0,95). `abrir()` guarda la ventana del frente (el juego) y toma el foco; `cerrar()` (el atajo de nuevo, Esc, "VOLVER AL JUEGO" en la barra `barra_overlay` o cerrar la ventana) la esconde, le devuelve sus flags/geometria (si estaba abierta antes, vuelve a la ventana de siempre, detras del juego) y el foco al juego. `MainMenuWindow._on_atajo`: segun `ajustes.overlay.modo` ("completo" por defecto, o "sala": la sala flotante chica de antes). La sala flotante sigue para los avisos (HUD) mientras se juega; al abrir el overlay se esconde. Tarjeta "Overlay encima del juego" en Ajustes. **El foco** (2026-10-20, Simon: encima del juego no se podia apretar nada, en el escritorio si): con el juego al frente Windows bloquea SetForegroundWindow y el juego, con su raw input, se quedaba con mouse y teclado; `overlay._poner_al_frente` se une un momento a la cola de entrada de la ventana del frente (AttachThreadInput) para pedir el foco, `_soltar_mouse` (ClipCursor(None)) suelta el cursor encerrado y `_tomar_el_foco` insiste hasta 6 veces (medido el 2026-10-20 con FC 26 abierto: foco y ventana bajo el cursor = el overlay, cursor visible; la ventana del juego es WS_POPUP 2560x1440 sin topmost, integridad media como la app). **Una sola app abierta** (`ui/instancia.py`, `UnaSola` con QLocalServer; solo el modulo menu): Simon tenia DOS abiertas (15:56 y 18:15) y el atajo era de la vieja, sin el arreglo; la segunda le avisa a la primera (`MainMenuWindow.traer_desde_otra`) y sale con 0; **Se cierra solo** si el juego vuelve al frente (alt-tab, click en el juego: `_si_volvio_el_juego`) o se minimiza, y `_traer_al_frente` (bandeja, icono) lo cierra antes de mostrar la ventana (Simon: quedaba la ventana normal con la barra del overlay); `pantalla_de_la_ventana` compara esquina y ancho (Qt 6 nombra las pantallas por el monitor, no DISPLAY1). Medido con SendInput: los clicks llegan a la app con el overlay encima del menu del modo carrera; **Simon juega con un mando de PS5 y la app no lee mandos** (con el overlay, el mando le sigue hablando al juego); al reiniciar, `EAFC_REINICIO` hace que la nueva espere a que la vieja se cierre. **CONFIRMADO por Simon el 2026-10-20: funciona encima del juego, tambien con el mando de PS5** (una vez se cerraba solo al rato y despues de reiniciar la app no volvio a pasar: `overlay.log` en la carpeta de datos anota cada apertura, el foco y QUIEN lo cerro -atajo, Esc, boton, circulo del mando, la ventana, el juego al frente, minimizar-; mirarlo primero si vuelve) (FC 26 en "ventana sin bordes"; en pantalla completa exclusiva no se puede sin engancharse al render) |
| `roleplay/ui/mando.py` | **El mando en el overlay completo** (2026-10-20, Simon juega con un DualSense y con el overlay el mando le seguia hablando al juego): `MandoOverlay` (lo crea el menu) prende `LectorMando` (SDL por pysdl2 + pysdl2-dll; se importa adentro; hints de fondo y SIN el modo mejorado del DualSense; busca mandos cada 1 s) solo con el overlay abierto, lee cada 16 ms y `Traductor` lo pasa a acciones: stick izquierdo = cursor (zona muerta 0,18, curva, 1600 px/s; cruceta 350 px/s para apuntar fino), X = apretar/soltar (mantener = arrastrar), circulo = volver al juego, stick derecho = rueda, L1/R1 = `MainMenuWindow.cambiar_seccion`. `RatonDeWindows` mueve el cursor (adentro de la ventana) y hace los clicks con SendInput SOLO si el overlay es la ventana del frente. `ajustes.overlay.mando` (casilla en Ajustes) lo apaga; `EAFC_SIN_MANDO=1` en las pruebas. El diagnostico dice que mando hay. El juego puede seguir leyendo el mando en segundo plano (eso es del juego) |
| `roleplay/ui/atajo.py` | `AtajoGlobal`: Ctrl+Shift+F12 con `RegisterHotKey` (ctypes) + `QAbstractNativeEventFilter`. Ojo: el tipo de evento llega como QByteArray (comparar con `bytes(tipo)`). Si la combinacion esta tomada, `registrar()` da False y la app sigue |
| `roleplay/ui/comun.py` | `ejecutar_en_hilo`, `esc` (escape HTML), `miles`, `fecha_corta`, `con_scroll` (pagina transparente) |
| `roleplay/ui/estilos.py` | Tema oscuro estilo EA FC: colores (unico lugar), `fuente_titulo()`, QSS, paleta forzada. **Todos los pop-ups con el diseno de la app** (2026-10-20, pedido de Simon): botones de Qt en espanol (`_en_espanol`: `qtbase_es` de PySide6), el boton por defecto de los pop-ups en verde (`QDialogButtonBox QPushButton:default`), menus (la bandeja), listas/tablas/encabezados, scroll horizontal, el explorador de archivos de Qt en vez del de Windows (`AA_DontUseNativeDialogs`: el nativo no toma el tema), y `_BarrasOscuras` (filtro de la app): cada ventana se abre con la barra de titulo oscura (`barra_oscura`: DwmSetWindowAttribute modo oscuro 20 y en Windows 11 el color de barra 35/borde 34/titulo 36; solo con la plataforma "windows") y cada calendario con los fines de semana en celeste (`calendario_con_estilo`) |
| `roleplay/ui/componentes.py` | `icono()` (SVG propios coloreados), `titulo_pagina`, `titulo_seccion`, `Tarjeta`, `Mosaico`, `chip`/`chip_tono`, `chip_alternable`, `fila` (None = estirable), `CartaJugador` (carta FUT pintada; nivel por reputacion: bronce <45, plata, oro >=70, elite >=85), `Avatar`, `FondoEstadio`, `agregar_noticia`, `limpiar_layout` |
| `roleplay/servicios/economia.py` | Vida y patrimonio: el sueldo real (`Carrera.sueldo_usuario`, campo `cmGX` de `mPrV`) se acredita con los dias del juego (`acreditar()`, neto 55%; la primera vez, lo cobrado desde el 1 de julio), catalogo sin marcas (casas, autos, relojes, moda, yate, jet) y donaciones; `efecto()` decide seguidores, reputacion, si es noticia y el tono (donar suma; presumir en mala racha resta, mas si es humilde/reservado); `repercusion()` (hilo) arma la noticia y los comentarios con `eventos.contar`. Todo en `estado_json.economia` **Desde el 2026-10-20**: tienda ampliada (casas, ropa, muebles sin marca; relojes y joyas con la marca en texto: Rolex, AP, Cartier), categoria `usados` (el marketplace), `valor_de_venta()` (los `nicho:` a su valor de hoy) y `acreditar()` suma los patrocinios (neto) |
| `roleplay/servicios/autos.py` | El concesionario (`Modelo.url_configurador`: la web oficial de cada modelo, sacada de los botones "Configure" de cada marca el 2026-10-15; SF90 y Roma ya no se venden y van al configurador general de Ferrari, Lamborghini y Rolls-Royce eligen el modelo adentro, Bugatti no tiene configurador y va la pagina del Tourbillon): modelos de marcas REALES (solo el nombre como texto; decision de Simon: la app es entre amigos; nunca logos ni modelos 3D de las marcas), precio base aproximado, opciones con recargo (`precio()`), `describir()` y `Configuracion` (se guarda como dict en el pedido) **Desde el 2026-10-20**: hiperautos de reserva Ferrari F80 (3.735.000, 45 dias), McLaren W1 (2.100.000, 42) y Porsche Mission X (2.800.000, 60; es un prototipo, Simon lo quiso igual), con la silueta `hiper_real`; el SF90 y el Roma pasaron a `DESCONTINUADOS` (siguen en `POR_ID` para los garages). **Revisado en las webs oficiales el 2026-10-20 (navegador)**: el Huracan ya no se vende (-> Temerario) y el 911 GT3 RS 992850 ya no esta en el configurador de Porsche (-> 911 GT3 S/C 992892): los dos a `DESCONTINUADOS`; sumados 12Cilindri, Amalfi y 849 Testarossa; el F80 tiene configurador propio (`.../f80/default`); Revuelto y Urus SE al link directo del modelo; el AMG GT es el Coupe de 2 puertas (el 4 puertas ahora es electrico). Los demas links cargan bien (McLaren `?model/750s` redirige bien). **Aston Martin completo** (Simon, 2026-10-20): los 15 que se configuran hoy (Vantage Coupe/Roadster/S/S Roadster, DB12 Coupe/Volante/S/S Volante, DBX GT/S/707, Vanquish Coupe/Volante, Valhalla, Valen), cada uno al configurador de su familia (`/CL/model-select/M.../AM...`; la version se elige adentro). Su configurador NO da precios: aproximados en libras (DB12 Volante 199.500 y S Volante 224.000 de Car Magazine / What Car, DBX S 210.000, Valen ~1,5 M de la prensa; el resto de lanzamiento). **Todas las marcas completas** (2026-10-20, 81 modelos): lo que se configura en cada web (Ferrari 13, Porsche 24 -los codigos se leyeron del titulo de cada pagina del configurador-, Aston 15, Bentley 7 con Torcal, McLaren 6, AMG 4, Rolls 4, Range Rover 4 con Sport/Velar/Evoque, Lamborghini 3, Bugatti 1). El 718 de Porsche no aparecio en el configurador de Chile. Precios aproximados en libras (Torcal 173.300 y Luce ~550.000 euros de la prensa). `MODELOS` se ordena por marca al final |
| `roleplay/ui/configurador.py` | `Configurador` (QDialog): a la IZQUIERDA la web oficial de la marca adentro de la app (`crear_navegador` -> `ui/navegador.py`), a la DERECHA el panel del juego (pintura, llantas, pinzas, franjas, interior, extras, patente, precio y PEDIR). La foto del garage: "CAPTURAR VISTA" (con `RecortarFoto` para quedarse con el auto), "Pegar imagen" del portapapeles, o se saca sola al pedir; `guardar_foto` la deja en `config.CARPETA_GARAGE` (<id del pedido>.jpg, 960 de ancho) y `miniatura()` la muestra en Vida (o el dibujo si no hay foto). Sin navegador (sin pantalla, o sin QtWebEngine) queda el dibujo: `svg_auto(config)` con `SILUETAS`, 14 carrocerias **calcadas a mano de fotos reales de perfil** (el archivo de origen va en un comentario arriba de cada una). Solo el contorno: nunca logos ni modelos 3D de las marcas ni de GTA. **QtSvg no soporta clip-path**: franjas y fibra van como cortes del degradado (`_pintura`), y los parantes se cortan contra la ventana (`_ventana_en`). Con la pantalla al 300%, las imagenes se escalan con `_nitida` (si no, se ven a un tercio) |
| `roleplay/ui/tienda.py` | **La tienda real** (Pilar 3, 2026-10-20): `DialogoTiendaReal(categoria, saldo, moneda)` como el configurador: a la izquierda la web oficial adentro (`crear_navegador`), un boton por tienda de `tiendas.TIENDAS[categoria]` (relojes: configurador de Rolex, AP, Cartier; ropa: Nike By You, Gucci, Louis Vuitton, Balenciaga, Farfetch; tambien casas, yates, aviones, tecnologia, muebles; las de relojes y ropa revisadas en el navegador el 2026-10-20); a la derecha nombre, precio ("Leer de la pagina": `SCRIPT_METADATOS` con `runJavaScript` -> `leer_metadatos` en la moneda del juego; o un nivel de `NIVELES`), la foto ("Capturar vista" + `RecortarFoto`) y COMPRAR (solo si alcanza). Sin navegador, el formulario y "abrir en tu navegador". `guardar_foto_compra` -> `config.CARPETA_COMPRAS` (compras/). En Vida: boton "Comprar en las webs oficiales" en cada categoria con tiendas (`abrir_tienda_real` -> `comprar_de_tienda(articulo, url, foto)`: posesion `libre:<categoria>` con url y foto, que "Lo que tenes" muestra). La categoria `moda` se llama "Ropa y moda". **Arreglado el 2026-10-20** (Simon: la ropa no andaba y los yates no leian el precio): (1) `runJavaScript` devolvia "" con el objeto del script (listas de objetos no se convierten), asi que "Leer de la pagina" NUNCA leia nada: ahora `SCRIPT_METADATOS` devuelve `JSON.stringify(...)` y `tiendas.datos_de_script` lo abre; los precios numericos van como numero (con 3 decimales se leian por mil) y si no hay schema.org, `precio_texto` (el primer precio escrito en la pagina, `precio_en_texto`). Verificado con QtWebEngine real en JamesEdition (Solaris 111RS US$21,6 M, VanDutch 40 US$325.000). (2) Gucci, Louis Vuitton, Dior, Farfetch (y Mytheresa, Adidas) dan "Access Denied" a CUALQUIER navegador integrado (no es el user agent: probado); no se esquiva: `Tienda.adentro=False` las abre en el navegador de siempre (y cualquier pagina que conteste "Access Denied" tambien), con "Pegar foto" del portapapeles. Ropa que SI anda adentro: Nike By You, Balenciaga, Prada, Versace, Moncler, Palm Angels, Zara |
| `roleplay/ui/navegador.py` | El navegador integrado (QtWebEngine): `Navegador(url)` con atras, recargar y "abrir en tu navegador"; perfil persistente en `<datos>/navegador` (el aviso de cookies se contesta una vez); los enlaces a otra ventana se abren en la misma; `foto()` devuelve lo que se ve en pixeles de verdad. **Se importa recien al abrir el configurador** (TestArranque vigila que abrir la app no cargue QtWebEngine) y `app.py` pone `AA_ShareOpenGLContexts` antes de crear la QApplication. **No se tocan encabezados de seguridad**: la web es la pagina principal (no un iframe), asi que X-Frame-Options/frame-ancestors no aplican. Sin pantalla (offscreen, las pruebas) `disponible()` es False: Chromium no dibuja y la foto saldria en blanco (tampoco con la ventana oculta: para probarlo de verdad, una ventana visible fuera de la pantalla) |
| `scripts/trazar_silueta.py` + `docs/siluetas.md` | Como se calca un auto nuevo: buscar la foto de perfil en Commons, medirla en el navegador (`medirAuto` automatico o la rejilla `ver()` a mano), y `trazar_silueta.py medidas.json --puntos --insertar <modelo> --fuente "..."` la pega en `SILUETAS`. Endereza la perspectiva (`perspectiva`, `ejes_sobre_radio`) y achica la escala si el auto es mas alto que el dibujo (G 63). Las medidas de cada auto quedan en `docs/siluetas/*.json` |
| `roleplay/servicios/amor.py` | Vida sentimental (`estado_json.amor`). Arranca del personaje (`estado_relacion`, `nombre_pareja`): novia real -> en pareja; celebridad o soltero -> soltero (la famosa es mas probable con "celebridad"). Sorteo semanal como los eventos (25%, semilla propia `amor:jugador:semana`): cena, tribuna, vacaciones (junio-julio), un viaje sorpresa, roces por tantos viajes, aniversario; con una famosa tambien alfombra roja, rumores de crisis, entrevista. **La novia real es una persona real**: solo momentos lindos o roces leves, nunca prensa del corazon, y lo negativo sale en tono neutral (sin titulares de "Polemica"). **Las famosas son INVENTADAS** (`NOMBRES` x `APELLIDOS` x `OFICIOS`): nunca personas reales. Decisiones: hacerlo oficial o negarlo, proponer casamiento (relacion >= 80 y 180 dias; el anillo cuesta 6 semanas), la boda (a los 120 dias: a lo grande o intima) y la crisis (< 25). Tarjeta "Vida sentimental" en Vida **Desde el 2026-10-20**: las famosas salen del catalogo de Simon (`famosas_ig.json`, ver `ecosistema.py`; sin el, inventadas). Soltero: `buscar()` y `intentar()` (un DM por semana del juego): si `calcular_fama_jugador` alcanza la `exigencia`, decision `como_seguir` (secreto u oficial); si no, visto (con diferencia >= 25, chisme publico y reputacion -1). **Desde la segunda pasada del 2026-10-20**: el DM es con azar, `probabilidad_de_exito(fama, exigencia)` (85% al alcanzarla, +-3% por punto, entre 3% y 97%) y, si lo deja en visto, `probabilidad_de_filtracion` (desde 10 puntos de diferencia; la captura llega a los portales de chismes, y en el feed la publica la pagina de farandula, @tmz_tv en los datos de Simon); `intentar(..., dado=)` para las pruebas. `oficializar()`: un romance secreto se hace publico cuando quiera (boton "Oficializar relacion" en Vida) Estado `secreto`: momentos `privado` (sin prensa), cruce `rumor_secreto` para los periodistas y a los 30 dias la decision `salir_a_la_luz`. `revisar(..., fama)`: "lo ven con" alguien de su nivel **Con la pareja (2026-10-20, como BitLife)**: `ACCIONES` (cena, regalo, regalo de lujo, escapada, foto juntos, y casados una sola vez la foto de la boda; cada una una vez por semana del juego, cuesta semanas de sueldo -`costo_de`, sin plata no se puede- y sube la relacion; en secreto no se publica la foto y lo demas es privado), `interactuar()`, `proponer()`/`casarse()` cuando se cumple el tiempo y la relacion (botones en Vida, ademas de la decision que llega sola), `terminar()` cuando quiera (casado: divorcio, 10 semanas; con persona real, tono neutral). La foto va como POST de verdad en su Instagram (`instagram.post_con_pareja` del corpus `post_pareja_*`/`post_boda_*`, editable, y `reaccion_post_con_pareja`: x2, x4 con una famosa). El titulo de un suceso de decision es lo que paso ("Hizo publico su romance con..."), no el texto del boton, y la noticia lleva "{Apellido} {detalle}". **Familia (2026-10-20)**: "Armar una familia" (`hablar_de_hijos`, en pareja/comprometido/casado, relacion >= 50): casi siempre si; a veces "todavia no" (`chance_de_no`: con una famosa 20%, por su carrera; con la novia real 8%; +10% si la relacion esta bajo 65; se puede volver a hablar a los 120 dias) o "nunca" (7% / 4%, para siempre con esa pareja). La charla es privada. Si dice que si, `embarazo` (3% mellizos); a los 270 dias (o ya, en la de prueba) "Llego el dia: ir al hospital" -> `parto(..., nombre_para)` (el usuario elige el nombre; sugerido de `NOMBRES_BEBE`), noticia `amor:nacimiento`, 3 semanas de sueldo. `estado.hijos` queda aunque terminen; el embarazo tambien. Accion "Foto en familia" con hijos (`post_familia_*`) |
| `roleplay/servicios/clubes.py` | Tu hinchada: carino (0-100) de la hinchada de cada club (`estado_json.clubes`). Arranca en 50; cada partido del club lo mueve (ganar +1, perder -1, cada gol +2 hasta 6, nota >= 8 +2, < 6 -2) y los eventos inesperados tambien (`por_evento`). El club sale del CONTRATO (`club_de`), no de los partidos: un traspaso se ve apenas se firma. Al cambiar de club: salida como idolo (>= 70), normal o por la puerta de atras (<= 30); si eras idolo y te vas a un club de LA MISMA LIGA, traidor (-30; la partida no guarda rivalidades); volver a un club te recibe segun como te fuiste. Decisiones (`DECISIONES`): hinchada en contra (< 25), polemica (despues de la polemica en redes o la fiesta del yate) y un grande que pregunta por el idolo (>= 85 y reputacion >= 70, una vez por temporada); `elegir()` mueve carino, reputacion y seguidores y puede traer un reto. Se contestan en el Resumen (tarjeta "Tu hinchada"); todo es noticia via `eventos.contar()` |
| `roleplay/servicios/eventos.py` | Eventos inesperados, buenos y malos (multa con su auto, choque, robo en su casa, fiesta filtrada en el yate, gripe, molestias, multa del club, polemica en redes, hinchas que lo increpan; campana publicitaria, video viral, visita a un hospital, TV, jugador del mes, la camiseta a un nene). `revisar()` sortea una vez por SEMANA del juego (30%, semilla jugador+semana: la misma partida da los mismos eventos), a lo sumo uno por revision, con reglas (`requiere`: auto/casa/yate/mala_racha/buena_racha/reputacion:N; `pesos` por personalidad; no repite los ultimos 4). El codigo decide reputacion, seguidores (la escala de la hinchada) y plata (semanas de sueldo neto); `contar()` (hilo; la usan tambien la economia, la hinchada y el amor) arma noticia (`t_vida_<tono>` + la descripcion + `c_vida_<tono>`) y comentarios. Algunos traen un `reto` de roleplay (arrancar en el banco, no jugar el proximo): la app no toca el juego, es una propuesta. `estado_json.eventos` |
| `roleplay/ui/vida.py` | `PaginaVida`: saldo, sueldo neto, gastos fijos, patrimonio; tienda por categoria, lo que tenes (vender al 70%), filantropia y movimientos. `acreditar_con(carrera)` la llama el menu en cada autoguardado (cobra, entrega autos y sortea los eventos inesperados: tarjeta "Lo que te paso" y aviso en la bandeja con `evento_inesperado`). Los botones se identifican por la propiedad `articulo` (el objectName es el del estilo) **Desde el 2026-10-20**: tarjeta Patrocinios (contratos y la oferta con Firmar/Rechazar), el marketplace en "Usados y de culto" (foto con `miniatura_de_archivo`), tarjeta aparte "Explorar Instagram VIP" (solo soltero: buscador, filtro por categoria, % de chance y de filtracion por celebridad, "Enviar DM"), boton "Oficializar relacion" con un romance secreto y `_fila_ancha` (texto largo con botones sin partirse en una columna) |
| `roleplay/servicios/metas.py` | Metas de temporada que se propone el usuario (`estado_json.metas`: goles, goles en liga, asistencias, top N de la liga). `evaluar_metas()` las decide con la partida (contables apenas se llega; el puesto al terminar la liga; las de una temporada pasada fallan); las entrevistas y la prensa las conocen por `cruce.py` (la meta a punto de cumplirse o complicada). La prensa devuelve `resultado["metas"]` y la sala lo guarda con `database.actualizar_metas` (que no revive una meta borrada) |
| `roleplay/servicios/mercado.py` | Fichajes reales: `clubes_de_jugadores(carrera)` (hombres, club de hoy) contra la foto anterior de la misma partida (tabla `club_visto`, `database.get/guardar_clubes_vistos`) -> `detectar_traspasos()` (noticia: tu club, media >= 82, o tu liga con media >= 75), `traspaso_del_usuario()` (hito `nuevo_club`). La foto se guarda recien despues de armar la prensa: si algo falla, se detectan de nuevo |
| `roleplay/servicios/previa.py` | Conferencia PREVIA al proximo partido: `previa_del_proximo(carrera)` arma los datos reales (tabla de los dos, rachas, ultimo partido del rival, cruces de la temporada, goleador rival; `ya_hecha` con `estado_json.partida.previa`), `generar_previa` / `evaluar_previa` (los mismos periodistas y el mismo evaluador; `BASE_PREVIA` sin resultado, delta acotado a ±10, titular con la cita si hay) y `noticia_de_previa`. NO se guarda como partido (no suma PJ ni goles) |
| `roleplay/servicios/temporada.py` | `vista_temporada(carrera, competicion)`: lo que muestra la pagina Temporada (tabla con el club marcado, goleadores con el jugador del usuario marcado, resultados y proximos del club, la ultima fecha). Liga primero; una competicion ajena cae en la del club |
| `roleplay/ui/temporada.py` | `PaginaTemporada`: chips para elegir competicion, tabla (QGridLayout de QLabel; la fila del club lleva un QFrame resaltado DEBAJO, en la misma celda), goleadores, tus partidos y la ultima fecha. Si se cambia de competicion mientras lee, vuelve a leer al terminar |
| `roleplay/ui/menu.py` | `MainMenuWindow(pagina_inicial)` (lateral con JUGAR FC 26 y AJUSTES + `FondoEstadio`) + `PaginaResumen` (carta, mosaicos, historia, tramas, central de noticias) |
| `roleplay/ui/ajustes.py` | `DialogoAjustes` (juego, partida, modo en vivo, "Tus carreras" (lista, "Cambiar a esta" reinicia, "Nueva carrera..." con nombre y su partida CmPlr), "Motor narrativo e IA hibrida": claves de Groq y Gemini en modo password, "Usar solo motor local", "Probar IA" en un hilo con proveedor y ms; iconos, diagnostico), `abrir_juego_o_preguntar`. Ya no hay bienvenida |
| `roleplay/ui/personaje.py` | `CharacterWizard` (ClassicStyle; titulos en rich text con "PASO n/8"; backstory editable o escrito a mano) |
| `roleplay/ui/entrevista.py` | `InterviewWindow` "Sala de prensa": marcador ("Cargar de mi partida" o a mano; no hay captura) -> preguntas de los 3 periodistas (cada una con boton de voz) -> reaccion -> prensa. Despues de evaluar, `_mover_carino()` aplica `delta_carino` a la hinchada del club |
| `roleplay/ui/instagram.py` | `InstagramWindow`: perfil (avatar + mosaicos), nuevo post, resultado, "Tus hinchas" (actividad sin publicar) y feed en tarjetas. `revisar_hinchada()`: una a la vez; si se pide otra mientras corre, se hace al terminar **Desde el 2026-10-20**: tarjeta "Feed global" (`estado_json.hinchada.feed`). En los posts, `servicios/instagram.comentarios_del_ambiente`: colegas de `futbolistas_ig` si la fama supera su `fama_minima_para_comentar`, la pareja del catalogo (un guino si es secreto, y los hinchas lo notan), una celebridad de su nivel SOLO de `CATEGORIAS_QUE_COMENTAN` (deportista: una cantante o actriz sin relacion con el futbol no comenta; pedido de Simon 2026-10-20) y hasta 3 likes verificados (mismo filtro) (comentario con tono "like"). Esos comentarios los arma el codigo con el corpus, nunca la IA |
| `roleplay/servicios/hinchada.py` | El Instagram que se mueve solo: `eventos_nuevos()` (partidos del usuario y noticias sobre el desde `estado_json.hinchada`; la primera vez solo el ultimo partido), `crecimiento_por_partido/noticia()` (los seguidores los decide el codigo), `comentar_eventos()` y `comentarios()` (2-3 del corpus: el tono sigue a los seguidores, con algun gracioso o rival). **Una reaccion por cosa** (2026-10-20, Simon: las primas y las marcas salian dos veces, la segunda con +900.000 seguidores): las noticias que arma `eventos.contar` (claves `eventos.CON_REACCION_PROPIA`: evento, amor, patrocinio, contrato, oferta, hinchada, compra, donacion) ya traen su actividad, asi que `eventos_nuevos` las salta (`tiene_reaccion_propia`); `SISTEMA_HINCHAS` le prohibe a la IA citar seguidores o exagerar el titular. Se guarda en la tabla `actividad_instagram` **Desde el 2026-10-20**: `base_de_seguidores(tier)` (400.000 / 25.000 / 2.000 x reputacion): la primera vez o al pasar a un club de mejor tier, `procesar` suma la diferencia (actividad "hinchada", `estado.base_tier`); `exposicion(tier, goles, partidos, premios)` multiplica lo que mueve cada partido/noticia (80 goles en 40 en un gigante: x20 o mas, tope 40). `procesar` tambien arma el feed global (`estado.feed`, servicios/feed.py) |
| `roleplay/ui/iconos/` | Flechas/check de la QSS (SVG) y `app.ico` (lo genera el script del acceso directo) |
| `scripts/seed_test_matches.py` | Siembra/borra partidos "Rival de prueba N" en el ultimo personaje (base REAL) |
| `scripts/crear_acceso_directo.py` + `scripts/lanzador/Lanzador.cs` | Icono, .exe lanzador (dev) y los dos iconos del escritorio |
| `scripts/empaquetar.py` + `scripts/LEEME_AMIGOS.txt` | Paquete PyInstaller + zip para amigos (`--add-data` de `ui/iconos` y `roleplay/datos`; `podar_chromium`) |
| `scripts/nombres_faltantes.py` | `--catalogo-ea` baja el catalogo de EA (`drop-api.ea.com/rating/ea-sports-fc`, 100 por pagina; el orden de la API no es estable y con todo junto se saltea siempre a los mismos ~660, por eso recorre tambien `&gender=0` y `&gender=1` y suma; reintenta paginas cortadas) y muestra la cobertura; `--cobertura` solo la cobertura (el 2026-10-16, con la partida de Simon: 85% de los 21.507 jugadores, 96% de los goleadores, 585/597 de los que pueden ser noticia de mercado; lo que falta son agentes libres generados y ligas con nombres ficticios de EA como Brasil, India o Corea). Sin flags, lista los goleadores de las competiciones del usuario que no tienen nombre (id, club, posicion, seleccion, nacimiento) y `--agregar ID "Nombre"` los suma a `jugadores_fc26.json` con el nacimiento de la partida. **Solo nombres seguros**: el 2026-10-15 se verifico la base vieja contra la partida y la IA se habia equivocado en 8 de 20 (ej. el id de Vinicius Jr como Haaland; 851 era la Copa de Francia, no la Ligue 1) |
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
  partida no trae salen de la base local (`roleplay/datos`: la de a mano, el catalogo de EA
  y el diccionario de ids de nombre). Un nombre que no esta (o cuyo
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
- Entrevista HECHA (`InterviewWindow._enviada`, desde 2026-10-16): al evaluarse, las respuestas quedan
  de solo lectura y `ocupada()` ya no la cuenta como a medias (antes el texto escrito trababa el cambio a
  la previa y el modo en vivo no cargaba el partido nuevo). `_ya_hecha()`: el partido de la partida que ya
  tuvo entrevista (`lectura.ya_entrevistado` con la misma fecha) o la previa ya dada (`previa.ya_hecha`)
  no se vuelven a generar (boton "YA HICISTE ESTA ENTREVISTA" / "YA DISTE ESTA CONFERENCIA"); las stats a
  mano no tienen limite.
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
  partida; si no paso nada, no hay noticia). Las celebridades, periodistas, paginas y futbolistas
  reales salen SOLO de los datos de Simon (`ecosistema.py`; su responsabilidad, decidido el
  2026-10-19): el codigo los lee y los pone en textos genericos del corpus; Claude no escribe
  contenido sobre personas reales ni los agrega a esos archivos. Sin los datos, inventadas.

## Testing

`.venv\Scripts\python.exe -m unittest discover -s tests` (490 pruebas, ~50 s). `tests/ayuda.py`:
- Fija `EAFC_FC26_GUARDADOS` a una carpeta vacia: las pruebas no leen la partida real.
- Fija `EAFC_ECOSISTEMA` a una carpeta vacia: sin famosas, paginas, periodistas ni autos de nicho.
  `tests/datos_ecosistema.py` (datos chicos + `ConEcosistema`) los arma para `test_ecosistema` (base y pantallas),
  `test_amor` (DMs, chance, secreto), `test_instagram` (feed, colegas, likes), `test_autos` (hiperautos, marketplace),
  `test_entrevista` (periodistas con @, emocional, 8 temas) y `test_economia` (seguidores por tier, patrocinios).
- Fija `EAFC_CATALOGO_EA` a un archivo que no existe: los nombres no dependen del catalogo del PC
  (`test_nombres.py` arma el suyo).
- Fija `EAFC_SIN_MANDO=1`: ninguna prueba abre el mando de verdad (`test_mando.py` usa un lector falso).
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

**Noticias inventadas: SACADAS el 2026-10-16** (pedido de Simon del 2026-10-15). Ya no existen `prensa.noticia_de_ambiente`, `PROBABILIDAD_NOTICIA_GENERAL` ni el kwarg `incluir_general` (ni `solo_hechos` en la sala), y del corpus se fueron `t_general`/`c_general`/`#club_ficticio#`/`#jugador_ficticio#`/`#ciudad_ficticia#`. Las que ya estaban en la base de Simon (ids 2, 3, 4, 8, 9, 10 y 13 de `noticia_prensa`) se borraron con su si el 2026-10-16 (respaldo previo en `Proyecto Fifa
espaldo-db-antes-de-borrar-inventadas-2026-10-16.db`; la 7, el hat-trick de Grealish, se dejo).

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
3. Tienda universal: **HECHA el 2026-10-20** (la pantalla: `ui/tienda.py`; queda "Presumir en Instagram"). Antes: A MEDIAS (2026-10-15). Hecha la
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
