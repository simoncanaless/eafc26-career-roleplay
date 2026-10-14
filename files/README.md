# EAFC 26 Career Roleplay

**No modifica el juego**: corre al lado, como Discord u OBS. Lee la pantalla, nunca
los archivos ni la memoria de FC 26, asi que no lo puede romper y se puede jugar online.

Capa de roleplay narrativo para el Modo Carrera Jugador de EAFC 26: creas un
personaje con backstory, das entrevistas despues de cada partido, la prensa
reacciona a tus rachas y tu Instagram gana (o pierde) seguidores. La IA
(Gemini) redacta; los numeros (reputacion, hitos, seguidores) los decide el
codigo.

## Como correrlo

```powershell
.venv\Scripts\python.exe -m pip install -r requirements.txt
copy .env.example .env      # y pone tu GEMINI_API_KEY (gratis en https://aistudio.google.com/apikey)
.venv\Scripts\python.exe app.py
```

`app.py` abre el menu con todo. Con doble click: **`EAFC Roleplay.exe`** (en esta
carpeta) o el acceso **EAFC 26 Roleplay** del escritorio. Si no estan, se crean con:

```powershell
.venv\Scripts\python.exe scripts\crear_acceso_directo.py
```

Eso deja dos iconos en el escritorio:

- **EA FC 26**: el juego normal (por Steam, EA app o Epic, segun donde este).
- **EA FC 26 + Roleplay**: el mismo juego, y ademas la app abierta en la sala de prensa.

El .exe de esta carpeta es solo un lanzador: abre `app.py` con el Python del `.venv`,
asi que siempre corre el codigo actual. Si algo falla al abrir, el detalle queda en
`errores.log`; y `app.py --diagnostico` revisa clave, juego, microfono y captura.

## Para los amigos

```powershell
.venv\Scripts\python.exe -m pip install -r requirements-dev.txt   # una vez
.venv\Scripts\python.exe scripts\empaquetar.py
```

Deja `dist\EAFC Roleplay (amigos).zip` (~71 MB): descomprimir y abrir
`EAFC Roleplay.exe`, sin instalar Python. La primera vez pide la clave gratis de
Gemini de cada uno, y en Ajustes se crean los dos iconos. Sus datos quedan en
`%APPDATA%\EAFC26 Roleplay`. Instrucciones para ellos: `scripts\LEEME_AMIGOS.txt`
(va dentro del zip como `LEEME.txt`).

Para abrir un modulo suelto:

```powershell
.venv\Scripts\python.exe app.py personaje      # asistente de creacion de personaje
.venv\Scripts\python.exe app.py entrevistas
.venv\Scripts\python.exe app.py instagram
```

## Lee tu partida de FC 26

Si jugas Carrera Jugador, la app lee tu partida guardada (solo la lee: el juego no se
toca) y todo se vuelve real:

- **Sala de prensa**: "Tu ultimo partido: Man Utd 5-3 Sunderland" y un boton que llena
  el marcador, tus goles, tu nota y tus minutos. Las asistencias, tarjetas y figura salen
  comparando con la lectura anterior (el juego solo guarda totales).
- **Prensa**: noticias sobre lo que paso de verdad en tu mundo, con nombres: "Hat-trick
  de Grealish afianza al Manchester City en la cima de la Premier League". Que es noticia
  lo decide el codigo (hat-tricks, goleadas, choques de punta); Gemini reconoce a los
  jugadores por su ficha (club, posicion, seleccion, nacimiento) y redacta.
- **Resumen**: tu temporada real (partidos, goles, asistencias, nota por competicion, la
  tabla, la racha y el proximo rival) y tu club al dia.

**Modo en vivo**: con la app abierta mientras juegas, cuando el juego guarda un partido
nuevo te llega una notificacion de Windows ("Partido nuevo: Man Utd 2-1 Arsenal. Tu
entrevista te espera"), la sala de prensa ya tiene el partido cargado y las preguntas
listas, y la prensa reacciona. Las noticias sobre vos tambien salen de tus numeros
reales: 50 o 100 goles en la temporada, pasar a ser el goleador de la liga, un
partidazo, tu club lider o campeon. Se apaga en Ajustes > Modo en vivo.

Como funciona por dentro: `docs/partida-fc26.md`.

## Que hace cada modulo

1. **Personaje.** Un quiz (origen, contexto, personalidad, motivacion, vida
   sentimental, una anecdota). La reputacion inicial se calcula en codigo, y
   Gemini escribe el backstory y 3-5 *ganchos narrativos* (semillas de tramas).
   Todo queda editable antes de guardar, y si Gemini esta caido podes escribir
   el backstory a mano.
2. **Sala de prensa.** Capturas la pantalla de fin de partido (o escribis las
   stats a mano), Gemini arma 2-4 preguntas con tu perfil, respondes escribiendo
   o **por voz** (apretas "Responder por voz", hablas, lo apretas de nuevo y
   Gemini lo transcribe) y la prensa reacciona: cambia tu reputacion (hasta ±15
   por entrevista) y a veces nace un gancho nuevo.
3. **Prensa.** Despues de cada entrevista se revisa el historial: goles
   totales, rachas con y sin gol, y el rating promedio de los ultimos 5
   partidos disparan noticias sobre vos. A veces sale tambien una noticia de
   ambiente del mundo del futbol.
4. **Instagram.** Escribis un post y Gemini genera comentarios, likes y
   cuantos seguidores ganas o perdes, segun tu reputacion.

## Estructura

```
app.py                      punto de entrada unico
roleplay/
  config.py                 rutas (la base y el .env viven en la raiz del proyecto)
  models.py                 dataclasses + catalogos del quiz
  database.py               SQLite: career_roleplay.db
  gemini.py                 unico punto de contacto con Gemini (keys, fallback, JSON validado)
  servicios/                lo que se le pide a la IA y la logica que lo rodea
    contexto.py             como se le presenta el jugador a la IA (lo comparten todos los prompts)
    backstory.py  entrevista.py  prensa.py  instagram.py
    vision.py               lee las stats de la captura
    captura.py              captura de pantalla con dxcam (Windows)
    audio.py                grabar el microfono y transcribir
    juego.py                encontrar FC 26 (Steam/EA app/Epic) y abrirlo por su plataforma
    accesos.py              los dos iconos del escritorio
    partida_real.py         la partida de FC 26 en la app (ultimo partido, contexto, hechos)
    identificar.py          la IA pone nombre a jugadores y copas que la partida no nombra
  partida/                  leer el guardado de FC 26 (formato, carrera, lector)
  ui/                       pantallas (PySide6), estilo EA FC
    estilos.py              colores, tipografias y hoja de estilos (unico lugar)
    componentes.py          carta FUT, tarjetas, mosaicos, chips, iconos, fondo
    comun.py                hilos para la IA, formato de numeros/textos, scroll
    menu.py  personaje.py  entrevista.py  instagram.py  ajustes.py
scripts/seed_test_matches.py       siembra (o borra) 5 partidos de prueba
scripts/crear_acceso_directo.py    icono, EAFC Roleplay.exe y los dos iconos del escritorio
scripts/empaquetar.py              el paquete para los amigos
tests/                      pruebas automaticas
```

## Pruebas

```powershell
.venv\Scripts\python.exe -m unittest discover -s tests
```

Corren sin ventana, con una base temporal (nunca tocan `career_roleplay.db`),
sin llamar a Gemini y con un microfono falso. Lo que no cubren: la captura real
con dxcam, el microfono real y las respuestas reales de Gemini.

## Por que esta armado asi

- **`estado_json` en `player_profile`**: cada modulo guarda ahi su estado
  (reputacion actual y su historial, prensa, seguidores) sin migrar el esquema.
- **Salida estructurada**: toda llamada pide `response_schema` y valida con
  pydantic; nada de parsear JSON "prometido" en texto libre.
- **Varias keys y modelos**: si un modelo se queda sin cuota (429) se prueba el
  siguiente con la misma key; si una key no sirve (401/403), la siguiente key.
- **Arranque rapido**: Gemini, dxcam, OpenCV y el audio se cargan recien cuando se usan.
- **La carta cambia de color con tu reputacion**: bronce, plata (45+), oro (70+) y
  elite (85+), como los niveles de las cartas de FUT.
