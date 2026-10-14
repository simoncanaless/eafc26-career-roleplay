# EAFC 26 Career Roleplay

App de escritorio (Python + PySide6) que agrega una capa de roleplay narrativo al
Modo Carrera Jugador de EAFC 26: creacion de personaje con backstory, entrevistas
post-partido, prensa espontanea, Instagram ficticio y reputacion que evoluciona.
Proyecto personal de Simon (estudiante de Ing. Informatica, Chile). Corre en
Windows, desde `C:\Users\canal\Desktop\Proyecto Fifa\files`, con un venv en `.venv`
(Python 3.11.9).

## Como correrlo

```powershell
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe app.py                  # menu unificado
.venv\Scripts\python.exe app.py entrevistas      # o: personaje | instagram (modulo suelto)
.venv\Scripts\python.exe -m unittest discover -s tests
.venv\Scripts\python.exe scripts\seed_test_matches.py [--borrar]   # 5 partidos de prueba
```

Requiere un `.env` en `files/` con `GEMINI_API_KEY=...` (o `GEMINI_API_KEYS=k1,k2`).
Nunca imprimir, loguear ni pegar la key en ningun lado.

## Arquitectura

Reorganizado el 2026-10-14 (antes eran 18 archivos sueltos en la raiz; respaldo
del original en `Proyecto Fifa\respaldo-files-2026-10-14.zip`).

| Archivo | Rol |
|---|---|
| `app.py` | Unico entry point; argumento opcional para abrir un modulo suelto |
| `roleplay/config.py` | Rutas: `DB_PATH` y `.env` salen de la raiz del proyecto, no del cwd |
| `roleplay/models.py` | Dataclasses `PlayerProfile`, `MatchInterviewRecord`, `NoticiaPrensa`, `InstagramPost` + catalogos del quiz |
| `roleplay/database.py` | SQLite. Mapeo GENERICO dataclass <-> fila (`TABLAS`, `_insertar`, `_desde_fila`); `_editar_estado` para leer-modificar-escribir `estado_json` en una transaccion |
| `roleplay/gemini.py` | **Unico punto de llamada a Gemini**: `generar_json(prompt, Esquema, que_hacer, imagen_png=None)` sobre `generate_content_with_fallback` |
| `roleplay/servicios/contexto.py` | `ficha_jugador(perfil, backstory=, ganchos=)`: como se describe el jugador en TODOS los prompts |
| `roleplay/servicios/backstory.py` | Backstory + ganchos narrativos |
| `roleplay/servicios/entrevista.py` | Preguntas y evaluacion de respuestas (reaccion + delta de reputacion, tope ±15) |
| `roleplay/servicios/prensa.py` | Hitos deterministas (rachas, goles, rating ultimos 5) + noticias del jugador y de ambiente |
| `roleplay/servicios/instagram.py` | Comentarios, likes, seguidores de un post |
| `roleplay/servicios/vision.py` | `MatchStats` + lectura de la captura con Gemini Vision |
| `roleplay/servicios/captura.py` | Captura con dxcam (Windows only), import perezoso |
| `roleplay/ui/comun.py` | `ejecutar_en_hilo`, `esc` (escape HTML), `miles`, `fecha_corta`, `con_scroll` |
| `roleplay/ui/estilos.py` | Paleta forzada clara + QSS compartido (incluye flechas de spinbox en `ui/iconos/`) |
| `roleplay/ui/menu.py` | `MainMenuWindow` (sidebar) + `PaginaResumen` |
| `roleplay/ui/personaje.py` | `CharacterWizard` (quiz; backstory editable o escrito a mano) |
| `roleplay/ui/entrevista.py` | `InterviewWindow`: captura o stats a mano -> preguntas -> respuestas -> reaccion -> prensa |
| `roleplay/ui/instagram.py` | `InstagramWindow` |
| `scripts/seed_test_matches.py` | Siembra/borra partidos "Rival de prueba N" en el ultimo personaje (base REAL) |
| `tests/` | `ayuda.py` (base temporal, Gemini bloqueado, dialogos mudos) + `test_*.py` |

## Convenciones (respetarlas)

- **Toda llamada a Gemini pasa por `gemini.generar_json`**, que pide
  `response_mime_type="application/json"` + `response_schema=<modelo pydantic>` y
  valida. `que_hacer` es la frase final del error ("apreta X de nuevo"). No
  hardcodear "error 503".
- Fallback: 429 -> siguiente modelo con la misma key; 401/403 -> siguiente key; 5xx ->
  siguiente modelo; otros (400) fallan rapido. Usar `exc.code` (int), **no** `exc.status`.
  El SDK reintenta solo 5xx (3 intentos); el 429 NO se reintenta (era ~1 min de espera
  por modelo con la cuota diaria agotada). Sin key: `FaltaApiKey`, sin "reintenta".
- `google.genai`, `dxcam` y `cv2` se importan DENTRO de las funciones (arranque 1,9 s -> 0,35 s).
  `tests/test_ui.py::TestArranque` falla si alguien los vuelve a importar arriba.
- **Toda llamada a la API desde la UI usa `ui.comun.ejecutar_en_hilo(func, *args,
  al_completar=metodo, al_fallar=metodo)`**. Nada de clases QThread nuevas ni de
  guardar el hilo en un atributo: el registro `_TareasVivas` lo mantiene vivo hasta
  que termina. Pasar METODOS de la ventana, no lambdas (PySide desconecta los metodos
  si la ventana se destruye).
- Lo que se manda a la IA y vuelve despues se guarda contra el jugador/datos de ESE
  momento (ver `_evaluando`, `_prensa_player_id`, `_publicando`), no contra
  `self.perfil` ni el formulario actual.
- Botones de la entrevista: solo `_refrescar_botones()` decide cuales estan activos.
- Todo texto de la IA o del usuario que va a un QLabel con formato pasa por `esc()`;
  un `<3` sin escapar se comia el resto del comentario.
- Numeros con separador de miles: `miles(n)`. Nunca `.replace(",", ".")` sobre un
  f-string entero (se comia las comas del nombre del club).
- Lo que genera la IA queda **editable** antes de guardarse (backstory, ganchos, stats).
- Estado de modulos nuevos va en `player_profile.estado_json` (ej: `reputacion_actual`,
  `historial_reputacion`, `prensa`, `seguidores_instagram`) para no migrar el esquema.
  Columnas nuevas reales: agregarlas al `SCHEMA` **y** a `COLUMNAS_AGREGADAS`
  (la DB del usuario ya existe y tiene datos). Un campo nuevo en un dataclass necesita
  su columna: el mapeo generico falla fuerte si falta.
- Las paginas del menu exponen `actualizar()`, que recarga el perfil; el menu lo llama al navegar.
  Cada pagina va dentro de `con_scroll`.
- Estilo: `estilos.aplicar_estilo(app)`; no redefinir paletas por ventana.
- Strings de UI en espanol (voseo/chileno informal), sin tildes en el codigo.
- Los prompts piden no inventar nombres de personas/jugadores reales.

## Testing

`.venv\Scripts\python.exe -m unittest discover -s tests` (47 pruebas, ~4 s). `tests/ayuda.py`:
- `PruebaConBase`: base temporal por prueba (`config.DB_PATH` parcheado).
- `PruebaDeInterfaz`: + QApplication offscreen + `QMessageBox.information/warning` mudos (en `self.avisos`).
- Gemini queda bloqueado: si algo llama a `_cliente` de verdad, la prueba falla.
  Mockear `generar_json` en el modulo del servicio (ej. `roleplay.servicios.prensa.generar_json`).
- `esperar_tareas()` en vez de `hilo.wait()` + `processEvents()`.
- `correr_aislado(codigo)`: para escenarios que, si fallan, cierran el proceso
  (QThread destruido corriendo => exit 127 sin mensaje).
- Capturas de pantalla offscreen: `QT_QPA_FONTDIR=C:/Windows/Fonts`, si no salen cuadraditos.
- No probado automaticamente: captura real con dxcam y respuestas reales de Gemini.

## Gotchas conocidos

- Windows en modo oscuro deja labels invisibles si no se fuerza la paleta (por eso `estilos.py`).
- `.env` en Windows suele quedar como `.env.txt`; crearlo desde VS Code.
- Paths en PowerShell: `.venv\Scripts\python.exe`, no `/c:/...`.
- Tier gratis de Gemini: 503 por demanda y 429 por cuota son frecuentes; el fallback lo maneja.
- dxcam usa OpenCV por dentro para convertir colores: `opencv-python` no se puede sacar.
- Los hitos de rating (buen/mal momento) exigen 5 partidos: antes, con 0 partidos el
  promedio era 0.0 y salio una noticia falsa de "mal momento" (noticia #1 de la base de
  Simon, con `prensa.rating_bajo_min_reportado = 5.0` que quedo de ese bug).
- Hay una copia vieja identica del codigo original en `C:\Users\canal\Documents\files`.

## Estado / roadmap

Hecho:
1. Quiz de personaje + backstory editable (o escrito a mano)
2. Entrevistas post-partido (captura + Gemini Vision, o stats a mano; reaccion + reputacion evolutiva)
3. Prensa: hitos del jugador + noticias generales del mundo
4. Instagram: posts, comentarios, likes, seguidores
5. Menu unificado con estilos compartidos y scroll por pagina
6. Pruebas automaticas (unittest)

**No existe** (la version anterior de este documento lo daba por hecho): respuestas
por voz / `audio_service.py` (grabar del microfono y transcribir con Gemini).

Pendiente (ideas del usuario):
- Respuestas por voz en la entrevista
- Reputacion por club + eventos de decision (quedarse/irse tras una polemica, clubes que no te quieren por tu historial)
- Economia / lifestyle (casas, autos, yates, aviones, joyas, ropa) con efecto en la imagen publica
- Filantropia (hospitales, comunidades, fundaciones)
- Eventos inesperados (lesiones, accidentes, enfermedades; buenos y malos)
- Vida sentimental: novia real vs posibilidad de relacion con una famosa, con tramas

## Como trabajar con Simon

- Respuestas directas y practicas, en espanol.
- A veces implementa partes el mismo: antes de reescribir algo, revisar lo que ya hizo y
  preguntar si hace falta. Si pide revision, revisar y corregir bugs reales (con prueba que los demuestre).
- Entregar cambios probados; avisar explicitamente lo que no se pudo probar (dxcam, microfono real).
