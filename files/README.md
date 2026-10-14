# EAFC 26 Career Roleplay

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

`app.py` abre el menu con todo. Para abrir un modulo suelto:

```powershell
.venv\Scripts\python.exe app.py personaje      # asistente de creacion de personaje
.venv\Scripts\python.exe app.py entrevistas
.venv\Scripts\python.exe app.py instagram
```

## Que hace cada modulo

1. **Personaje.** Un quiz (origen, contexto, personalidad, motivacion, vida
   sentimental, una anecdota). La reputacion inicial se calcula en codigo, y
   Gemini escribe el backstory y 3-5 *ganchos narrativos* (semillas de tramas).
   Todo queda editable antes de guardar, y si Gemini esta caido podes escribir
   el backstory a mano.
2. **Entrevistas.** Capturas la pantalla de fin de partido (o escribis las
   stats a mano), Gemini arma 2-4 preguntas con tu perfil, respondes con tus
   palabras y la prensa reacciona: cambia tu reputacion (hasta ±15 por
   entrevista) y a veces nace un gancho nuevo.
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
  ui/                       pantallas (PySide6)
    comun.py                hilos para la IA, formato de numeros/textos, scroll
    estilos.py  menu.py  personaje.py  entrevista.py  instagram.py
scripts/seed_test_matches.py   siembra (o borra) 5 partidos de prueba
tests/                      pruebas automaticas
```

## Pruebas

```powershell
.venv\Scripts\python.exe -m unittest discover -s tests
```

Corren sin ventana, con una base temporal (nunca tocan `career_roleplay.db`) y
sin llamar a Gemini. Lo que no cubren: la captura real con dxcam y las
respuestas reales de Gemini.

## Por que esta armado asi

- **`estado_json` en `player_profile`**: cada modulo guarda ahi su estado
  (reputacion actual y su historial, prensa, seguidores) sin migrar el esquema.
- **Salida estructurada**: toda llamada pide `response_schema` y valida con
  pydantic; nada de parsear JSON "prometido" en texto libre.
- **Varias keys y modelos**: si un modelo se queda sin cuota (429) se prueba el
  siguiente con la misma key; si una key no sirve (401/403), la siguiente key.
- **Arranque rapido**: Gemini, dxcam y OpenCV se cargan recien cuando se usan.
