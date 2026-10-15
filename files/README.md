# EAFC 26 Career Roleplay

**No modifica el juego**: corre al lado, como Discord u OBS. Lee tu partida guardada (solo
la lee), nunca escribe archivos ni toca la memoria de FC 26, asi que no lo puede romper y se
puede jugar online.

Capa de roleplay narrativo para el Modo Carrera Jugador de EAFC 26: creas un
personaje con backstory, das entrevistas despues de cada partido, la prensa
reacciona a tus rachas y tu Instagram gana (o pierde) seguidores.

**Sin IA**: los textos los arma un motor narrativo local (gramaticas en
`roleplay/datos/`), al instante, sin internet y sin ninguna clave. Los numeros
(reputacion, hitos, seguidores, carino) los decide el codigo.

## Como correrlo

```powershell
.venv\Scripts\python.exe -m pip install -r requirements.txt
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
`errores.log`; y `app.py --diagnostico` revisa el motor narrativo, el juego, el microfono
y el navegador del configurador.

## Para los amigos

```powershell
.venv\Scripts\python.exe -m pip install -r requirements-dev.txt   # una vez
.venv\Scripts\python.exe scripts\empaquetar.py
```

Deja `dist\EAFC Roleplay (amigos).zip` (~195 MB, casi todo el navegador de las webs de
las marcas): descomprimir y abrir `EAFC Roleplay.exe`, sin instalar Python ni poner
ninguna clave. En Ajustes se crean los dos iconos. Sus datos quedan en
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
  lo decide el codigo (hat-tricks, goleadas, choques de punta). Los nombres de los
  jugadores que la partida no guarda salen de una base local por id de EA
  (`roleplay/datos/jugadores_fc26.json`, con su fecha de nacimiento para no confundir a nadie;
  se completa a mano con `scripts/nombres_faltantes.py`);
  si alguien no esta, se lo describe ("el delantero centro del Manchester City"), nunca
  se inventa un nombre.
- **Resumen**: tu temporada real (partidos, goles, asistencias, nota por competicion, la
  tabla, la racha y el proximo rival) y tu club al dia.
- **Temporada**: la tabla de posiciones completa con tu club marcado, los goleadores
  (vos incluido), tus resultados y lo que viene, y la ultima fecha. Una pestana por cada
  competicion que juega tu club (liga, Champions, copas).

**Concesionario**: en VIDA > Autos estan los modelos de Ferrari, Porsche, Lamborghini, McLaren,
Mercedes-AMG, Rolls-Royce, Bentley, Aston Martin, Range Rover y Bugatti. Los configuras (color y
acabado, llantas, pinzas, franjas, interior, fibra de carbono, escape y patente personalizada)
al lado de la web oficial de la marca, que se abre adentro de la app para armar el auto real en
3D. Le sacas una foto (o se saca sola al pedir) y esa foto queda en tu garage. Lo pedis y
llega unos dias despues en el juego: ahi lo ven la prensa y
tus hinchas.

**Vida**: tu sueldo es el de tu contrato real en la partida (lo cobras a medida que pasan las
semanas del juego). Con eso compras casas, autos, relojes, ropa, un yate o un jet, o donas a
un hospital, una escuela de futbol o tu propia fundacion. Lo que hagas mueve tus seguidores
y tu reputacion: donar suma; presumir un jet en plena mala racha resta (mas si sos humilde).
Si es noticia, sale en la prensa, y los hinchas lo comentan en tu Instagram.

**Tu hinchada**: cada club tiene su carino por vos, que sube con tus goles y las victorias y baja
con las derrotas y las polemicas. Si te vas como idolo a un rival de la misma liga, tus ex hinchas
te tratan de traidor; si volves, te reciben segun como te fuiste. Y a veces te toca decidir: la
hinchada en tu contra (quedarte y ganartelos o pedir que te vendan), una polemica que no para
(disculpas o redoblar la apuesta), un grande que pregunta por vos. Esta en el Resumen.

**Vida sentimental**: arranca de lo que elegiste al crear el personaje. Con tu pareja pasan cosas
con las semanas del juego (una cena, la tribuna, vacaciones, roces por tantos viajes) y llegan las
decisiones: proponerle casamiento, la boda (a lo grande o intima), que hacer en una crisis. Si estas
soltero, te pueden ver con una famosa (inventada) y decidis si lo haces oficial. Esta en VIDA.

**Lo que te pasa**: a medida que pasan las semanas del juego te pasan cosas, buenas y malas: una
multa por exceso de velocidad (si tenes auto), una gripe, una polemica en redes (mas si sos
polemico), una campana publicitaria, un video viral... Mueven tu plata, tus seguidores y tu
reputacion, salen en la prensa, y algunas traen un reto para el proximo partido (por ejemplo,
arrancar en el banco). Estan en VIDA, en "Lo que te paso".

**Metas de la temporada**: en el Resumen te propones metas (goles, goles en liga, asistencias,
terminar entre los N primeros de la liga). Se siguen solas con tu partida, la prensa te
pregunta por ellas en las entrevistas, y cumplirlas o fallarlas es noticia y mueve tu
reputacion.

**Trayectoria**: cuando el juego pasa a la temporada siguiente, la prensa publica el balance
de tu temporada y queda archivada en el Resumen (club, partidos, goles, asistencias, nota,
posicion de tu club y titulos).

**Mercado de fichajes**: la app guarda en que club esta cada jugador de tu partida y, cuando
alguien cambia de club, es un traspaso: si toca a tu club, si es una estrella (media 82+) o
de tu liga, la prensa lo cuenta y aparece en TEMPORADA > Mercado de fichajes. Si el que
cambia de club sos vos, es la noticia del dia.

**Premios**: al pasar de mes en el juego, la prensa elige al jugador del mes de tu liga
(el que mas goles hizo en el mes, con datos reales). Si sos vos, es noticia y sube tu
reputacion; si no, es la noticia del mundo. Salir campeon o terminar como maximo goleador
tambien. Tus premios quedan en la VITRINA del Resumen.

**Conferencia previa**: en la sala de prensa, "Previa del proximo" arma una conferencia
antes de tu proximo partido con datos reales (los dos en la tabla, las rachas, si ya se
enfrentaron, el goleador rival). Respondes igual (escrito o por voz); la prensa saca un
titular con lo que dijiste y tu reputacion se mueve. No cuenta como partido jugado.

**Sala flotante**: un panel semitransparente encima del juego para hacer la entrevista
sin salir del partido (responder por voz, enviar, ver la reaccion y los titulares). Se
abre y se cierra con **Ctrl+Shift+F12** (funciona aunque el juego tenga el foco), desde el
icono de la bandeja, o solo al terminar un partido. Necesita FC 26 en "ventana sin bordes".

**Modo en vivo**: con la app abierta mientras juegas, cuando el juego guarda un partido
nuevo te llega una notificacion de Windows ("Partido nuevo: Man Utd 2-1 Arsenal. Tu
entrevista te espera"), la sala de prensa ya tiene el partido cargado y las preguntas
listas, y la prensa reacciona. Las noticias sobre vos tambien salen de tus numeros
reales: 50 o 100 goles en la temporada, pasar a ser el goleador de la liga, un
partidazo, tu club lider o campeon. Se apaga en Ajustes > Modo en vivo.

Y no hace falta que juegues vos: cada vez que el juego autoguarda (por ejemplo al simular
dias), la prensa cuenta lo que paso de verdad en el mundo (fichajes, premios, resultados) y
tu Instagram se mueve solo: en "Tus hinchas" reaccionan a tus partidos y a las noticias
sobre vos, y tus seguidores suben o bajan segun el resultado, tus goles y tu nota. Dejá el
autoguardado de FC 26 activado.

Como funciona por dentro: `docs/partida-fc26.md`.

## Que hace cada modulo

1. **Personaje.** Un quiz (origen, contexto, personalidad, motivacion, vida
   sentimental, una anecdota). La reputacion inicial se calcula en codigo, y
   el motor arma el backstory (tres parrafos con tus respuestas) y 3-4
   *ganchos narrativos* (semillas de tramas). Todo queda editable antes de guardar.
2. **Sala de prensa.** Cargas el partido de tu partida (o escribis las stats a
   mano) y tres periodistas te preguntan: uno tactico (numeros, la tabla, tu
   racha), una de Radio Tribuna (el vestuario, la hinchada, tus metas) y uno de
   El Picante (tus compras, tu pareja, lo que te paso). Se acuerdan de tus
   entrevistas anteriores: si cortaste una sequia, si bajaste el nivel, si ya
   enfrentaste a ese rival, si la fecha pasada sacaste pecho y hoy perdiste.
   Respondes escribiendo o **por voz** (el reconocimiento de voz de Windows en
   espanol, sin internet) y la prensa reacciona: cambia tu reputacion (hasta ±15
   por entrevista, ±10 en una previa) y el carino de tu hinchada, tu frase mas
   jugosa sale entre «» en la prensa y, si prometiste algo, queda de gancho.
3. **Prensa.** Despues de cada entrevista se revisa el historial: goles
   totales, rachas con y sin gol, y el rating promedio de los ultimos 5
   partidos disparan noticias sobre vos, cruzadas con el resto de tu vida (la
   compra cara en plena mala racha, la meta que esta cerca). A veces sale
   tambien una noticia de ambiente del mundo del futbol.
4. **Instagram.** Escribis un post y la app lo lee (humilde, polemico, para la
   hinchada...) y arma comentarios, likes y cuantos seguidores ganas o perdes,
   segun tu reputacion.

## El motor narrativo (sin IA)

- **Gramaticas** (`servicios/narrador.py` + `roleplay/datos/corpus_*.json`): cada texto es
  `[apertura] + [nucleo] + [cruce] + [cierre]`, con simbolos `#asi#` que se expanden y
  `{variables}` con los datos reales. Una alternativa solo entra si tiene todos sus datos.
- **No se repite**: por cada simbolo, los ultimos bloques usados no vuelven hasta usar los
  demas, y se recuerdan los ultimos 40 textos completos (`estado_json.narrador_usados`).
- **Cruces** (`servicios/cruce.py`): lo que pasa en tu vida entra en las preguntas y las
  noticias: el auto de £245.000 si jugaste para un 5.8, tu pareja en el palco, la meta a 2
  goles, el ex club que te trata de traidor, la multa de la semana pasada.
- **Evaluador lexico** (`servicios/lexico.py` + `roleplay/datos/lexico.json`): lee tus
  respuestas en cinco ejes (humildad y equipo, amor a la hinchada, ego, excusas y
  polemica, ambicion). Un "no", "nunca", "jamas" o "sin" en las dos palabras de antes
  invierte el peso ("no soy el mejor" no es ego).

## Estructura

```
app.py                      punto de entrada unico
roleplay/
  config.py                 rutas (la base y los ajustes de cada uno)
  models.py                 dataclasses + catalogos del quiz
  database.py               SQLite: career_roleplay.db
  datos/                    corpus del motor narrativo, lexico y bases de nombres (JSON)
  servicios/                la logica (hitos, economia, hinchada...) y el motor narrativo
    narrador.py             gramaticas + cola anti-repeticion (sin IA)
    lexico.py               evaluador de respuestas: cinco ejes, negaciones, la cita
    cruce.py                lo que pasa en el resto de la vida, para preguntas y noticias
    backstory.py  entrevista.py  previa.py  prensa.py  instagram.py  hinchada.py
    economia.py  autos.py  eventos.py  clubes.py  amor.py  metas.py  mercado.py
    vision.py               MatchStats (leer la captura con IA ya no existe)
    captura.py              captura de pantalla con dxcam (solo para el diagnostico)
    audio.py                grabar el microfono y transcribir (System.Speech, sin internet)
    juego.py                encontrar FC 26 (Steam/EA app/Epic) y abrirlo por su plataforma
    accesos.py              los dos iconos del escritorio
    partida_real.py         la partida de FC 26 en la app (ultimo partido, hechos, premios)
    identificar.py          nombres de jugadores y copas desde la base local
  partida/                  leer el guardado de FC 26 (formato, carrera, lector)
  ui/                       pantallas (PySide6), estilo EA FC
    estilos.py              colores, tipografias y hoja de estilos (unico lugar)
    componentes.py          carta FUT, tarjetas, mosaicos, chips, iconos, fondo
    comun.py                hilos para lo lento (leer la partida), formato de numeros/textos, scroll
    menu.py  personaje.py  entrevista.py  instagram.py  vida.py  configurador.py  ajustes.py
scripts/seed_test_matches.py       siembra (o borra) 5 partidos de prueba
scripts/crear_acceso_directo.py    icono, EAFC Roleplay.exe y los dos iconos del escritorio
scripts/nombres_faltantes.py       los goleadores de tu partida sin nombre, y --agregar ID "Nombre"
scripts/empaquetar.py              el paquete para los amigos
tests/                      pruebas automaticas
```

## Pruebas

```powershell
.venv\Scripts\python.exe -m unittest discover -s tests
```

Corren sin ventana, con una base temporal (nunca tocan `career_roleplay.db`) y
con un microfono falso. Como el motor narrativo es local, prueban los textos de
verdad: que no queden `{variables}` sin llenar, que no se repitan, que la
memoria quede en `estado_json`. Lo que no cubren: el microfono real y el
reconocedor de voz de Windows de verdad.

## Por que esta armado asi

- **`estado_json` en `player_profile`**: cada modulo guarda ahi su estado
  (reputacion actual y su historial, prensa, seguidores) sin migrar el esquema.
- **Sin IA**: nada que se caiga, sin cuota ni clave, al instante y offline. Los textos
  salen de corpus editables (`roleplay/datos/`): sumar frases es editar un JSON.
- **Arranque rapido**: dxcam, el audio y el navegador se cargan recien cuando se usan.
- **La carta cambia de color con tu reputacion**: bronce, plata (45+), oro (70+) y
  elite (85+), como los niveles de las cartas de FUT.
