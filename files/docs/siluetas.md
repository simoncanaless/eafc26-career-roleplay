# Siluetas de los autos (concesionario)

Cada auto del concesionario (`roleplay/servicios/autos.py`) se dibuja con una
`Silueta` de `roleplay/ui/configurador.py:SILUETAS`: el contorno de costado,
la ventana, las ruedas, faros, luces y detalles, en un dibujo de 400 x 170.

**Se calcan de fotos reales de perfil**, no se inventan: las primeras,
dibujadas a ojo, no se parecian a nada. Se calca el contorno y nada mas:
nunca el logo, el escudo ni la marca dibujada. Las fotos salen de Wikimedia
Commons; cada silueta lleva arriba, en un comentario, el archivo del que
salio, y sus medidas quedan en `docs/siluetas/*.json` para poder rehacerla
(el 911 se marco antes de que existiera `--insertar` y no tiene JSON).

## Buscar la foto

Sirve una foto de **perfil puro** (las dos ruedas como circulos), con
teleobjetivo y el auto entero. En Commons rinden las series "Seitenansicht"
(Dusseldorf, Ginebra) y las "... Side.jpg"; una foto de tres cuartos o con
gran angular deforma todo (el primer Aston salia alto y cuadrado por eso).
Busqueda por la API, desde una pestana de commons.wikimedia.org:

```js
const qs = ["McLaren 720S intitle:side", "McLaren 720S intitle:Seitenansicht"];
const r = await Promise.all(qs.map(q => fetch(`/w/api.php?action=query&list=search&srsearch=${encodeURIComponent(q)}&srnamespace=6&srlimit=20&format=json`).then(r => r.json())));
[...new Set(r.flatMap(x => x.query.search.map(s => s.title)))].join("\n")
```

Tambien sirven las categorias del tipo `Category:Side views of Mercedes-Benz
automobiles`. Para mirar varias candidatas a la vez se arma una grilla de
miniaturas con `Special:FilePath/<archivo>?width=300`.

## Medir

La foto se abre con
`https://commons.wikimedia.org/wiki/Special:FilePath/<archivo>?width=1280`
(redirige a thumb.wikimedia.org, y desde ahi el lienzo puede leer los pixeles).

**Auto de color fuerte sobre un fondo distinto** (el Huracan verde): medicion
automatica. `medirAuto({y0, y1})` devuelve, columna por columna, donde
empieza y termina la carroceria y la ventana; ese JSON va directo a
`python scripts/trazar_silueta.py medidas.json --nombre huracan`.

```js
window.medirAuto = function (opciones) {
  // opciones: {y0, y1} franja de la foto donde esta el auto (en pixeles de la imagen), {hue, tol} opcional
  const img = document.querySelector('img');
  const c = document.createElement('canvas'); c.width = img.naturalWidth; c.height = img.naturalHeight;
  const ctx = c.getContext('2d'); ctx.drawImage(img, 0, 0);
  const W = c.width, H = c.height, d = ctx.getImageData(0, 0, W, H).data;
  const hsv = (i) => { const r = d[i] / 255, g = d[i+1] / 255, b = d[i+2] / 255; const mx = Math.max(r, g, b), mn = Math.min(r, g, b), df = mx - mn;
    let h = 0; if (df) { if (mx === r) h = ((g - b) / df) % 6; else if (mx === g) h = (b - r) / df + 2; else h = (r - g) / df + 4; h *= 60; if (h < 0) h += 360; }
    return [h, mx ? df / mx : 0, mx]; };
  const y0 = opciones.y0 || Math.floor(H * 0.4), y1 = opciones.y1 || H - 1;
  let hue = opciones.hue;
  if (hue === undefined) { // el color dominante entre los pixeles saturados de la franja
    const caja = new Array(36).fill(0);
    for (let y = y0; y < y1; y += 2) for (let x = 0; x < W; x += 2) { const [h, s, v] = hsv((y * W + x) * 4); if (s > 0.45 && v > 0.3) caja[Math.floor(h / 10) % 36]++; }
    hue = caja.indexOf(Math.max(...caja)) * 10 + 5;
  }
  const tol = opciones.tol || 22, smin = opciones.smin || 0.35, vmin = opciones.vmin || 0.22;
  const es = (x, y) => { if (x < 0 || y < 0 || x >= W || y >= H) return false; const [h, s, v] = hsv((y * W + x) * 4); let dh = Math.abs(h - hue); dh = Math.min(dh, 360 - dh); return dh < tol && s > smin && v > vmin; };
  const cols = [];
  for (let x = 0; x < W; x += 3) {
    let top = -1, bot = -1;
    for (let y = y0; y < y1 - 2; y++) if (es(x, y) && es(x, y + 1) && es(x, y + 2)) { top = y; break; }
    if (top < 0) continue;
    for (let y = y1 - 1; y > top; y--) if (es(x, y) && es(x, y - 1) && es(x, y - 2)) { bot = y; break; }
    let mejor = 0, ini = -1, desde = -1;
    for (let y = top; y < Math.min(bot, top + Math.floor((bot - top) * 0.6)); y++) { if (!es(x, y)) { if (ini < 0) ini = y; } else if (ini >= 0) { if (y - ini > mejor) { mejor = y - ini; desde = ini; } ini = -1; } }
    cols.push([x, top, bot, mejor > 4 ? desde : -1, mejor > 4 ? mejor : 0]);
  }
  return JSON.stringify({W, H, hue, cols});
};
```

**Todo lo demas** (negro, plateado, fondo con ruido): a mano, con `--puntos`.
`ver(ix, iy, ancho)` agranda un pedazo de la foto con una rejilla rotulada en
pixeles de la foto, y los puntos se leen de la rejilla. Pedazos de 250 a 450
pixeles de ancho alcanzan.

```js
window.ver = function (ix, iy, iw, paso = 10) {
  // muestra la foto desde (ix, iy), iw pixeles de ancho, con una rejilla rotulada EN PIXELES DE LA FOTO
  const img = document.querySelector('img');
  const W = innerWidth, H = innerHeight, s = W / iw;
  img.style.cssText = `position:absolute;left:${-ix * s}px;top:${-iy * s}px;width:${img.naturalWidth * s}px;height:auto;margin:0;max-width:none`;
  let c = document.getElementById('rejilla');
  if (!c) { c = document.createElement('canvas'); c.id = 'rejilla'; c.style.cssText = 'position:fixed;left:0;top:0;pointer-events:none'; document.body.appendChild(c); }
  c.width = W; c.height = H; const g = c.getContext('2d'); g.font = 'bold 15px Arial';
  for (let x = Math.ceil(ix / paso) * paso; x < ix + iw; x += paso) { const px = (x - ix) * s, big = x % (paso * 5) === 0;
    g.strokeStyle = big ? 'rgba(0,255,255,.8)' : 'rgba(0,255,255,.3)'; g.beginPath(); g.moveTo(px, 0); g.lineTo(px, H); g.stroke();
    if (big) { g.fillStyle = '#ff0'; g.fillText(x, px + 2, 16); } }
  for (let y = Math.ceil(iy / paso) * paso; y < iy + H / s; y += paso) { const py = (y - iy) * s, big = y % (paso * 5) === 0;
    g.strokeStyle = big ? 'rgba(255,0,255,.8)' : 'rgba(255,0,255,.3)'; g.beginPath(); g.moveTo(0, py); g.lineTo(W, py); g.stroke();
    if (big) { g.fillStyle = '#ff0'; g.fillText(y, 2, py - 2); } }
};
```

Lo que lleva el JSON (todo en pixeles de la foto; ejemplo: `docs/siluetas/g63.json`):

| Clave | Que es |
|---|---|
| `frente`, `cola` | x de la punta delantera y de la trasera (si `frente > cola` el auto mira a la derecha y se espeja) |
| `suelo` | y donde apoyan las ruedas |
| `techo` | el contorno de arriba, **de la trompa a la cola** (se suaviza en curva) |
| `cola_abajo` | de la cola hacia abajo, hasta el arco de la rueda trasera |
| `frente_abajo` | desde el arco delantero hasta la trompa |
| `ruedas` | `[cx, cy, radio de la goma, radio del arco]`, la delantera primero |
| `piso` | y del zocalo (abajo de las puertas) |
| `ventana` | el poligono de los vidrios laterales |
| `asiento`, `parantes`, `puertas` | el respaldo que se ve, x de los parantes y de los cortes de puerta |
| `formas` | `faro`, `luz`, `detalles`, `aleron`: `[[puntos], relleno]`, con relleno `{vidrio}`, `{oscuro}`, `{cromo}` o un color. `detalles_svg`: SVG ya en coordenadas del dibujo (la C del Bugatti) |
| `perspectiva` | la rueda de atras se ve mas alta: se endereza |
| `ejes_sobre_radio` | foto casi de perfil: distancia entre ejes / radio de la rueda, de la ficha tecnica, y se rectifica |

Despues:

```
python scripts/trazar_silueta.py docs/siluetas/aston.json --puntos --insertar aston_db12 --fuente "Aston Martin DB11, Commons: ..."
```

y se compara el dibujo con la foto. Un auto alto (el G 63) no cabe a lo
ancho: el script achica la escala hasta que entra el techo y lo centra
(`tests/test_autos.py` revisa que ningun auto se salga del dibujo).

## Lo que no hay que olvidar

- Qt no dibuja `clip-path`: franjas y fibra de carbono van en el degradado de
  la pintura, y los parantes se cortan contra el borde de la ventana
  (`_ventana_en`).
- El pasarruedas oscuro es el mismo circulo del arco; en un todoterreno el
  zocalo queda **sobre** el eje y el arco es menos de media vuelta.
- Las fotos acortan un poco las puntas (estan mas lejos de la camara que las
  ruedas). Se deja asi: es como la gente conoce el auto.
- El navegador del panel a veces tarda en pintar despues de cambiar la
  rejilla: si la captura falla, se repite.

## De donde salio cada una

| Silueta | Modelos | Foto en Wikimedia Commons |
|---|---|---|
| `ferrari_super` | 296 GTB, SF90 | Ferrari 458 Italia berlinetta - port profile.jpg |
| `gt_ferrari` | Roma | Ferrari California T right side.jpg |
| `suv_deportivo` | Purosangue, Cayenne, Urus | Lamborghini Urus, Knightsbridge - geograph.org.uk - 5892143.jpg |
| `911_real` | 911 Carrera, Turbo S, GT3 RS | Porsche 991 Turbo S Seitenansicht.JPG |
| `sedan_real` | Taycan, AMG GT 63 | Porsche Taycan GTS (side view) (taken in 2022) (Kyoto, Japan).jpg |
| `huracan` | Huracan | Green huracan (20744807015).jpg |
| `cuna_real` | Revuelto | 2015 Lamborghini Aventador LP700-4 Pirelli Edition 6.5 Side.jpg |
| `super_real` | 750S, Artura | McLaren MP4-12C – Seitenansicht, 30. August 2012, Düsseldorf.jpg |
| `g_real` | G 63 | Mercedes-AMG G 63, GIMS 2018, Le Grand-Saconnex (1X7A0541).jpg |
| `suv_lujo_real` | Cullinan, Range Rover | 2023 Land Rover Range Rover SV Automatic 4.4 Side.jpg |
| `gt_rolls` | Spectre | 2023 Rolls-Royce Spectre EV - 102kWh (585PS) Electric - Wittering Blue - 06-2024, Side.jpg |
| `gt_lujo` | Continental GT | 2019 Bentley Continental GT Coupe 6.0 Side.jpg |
| `gt_aston` | DB12 | 2018 Aston Martin DB11 V8 Automatic 4.0 Side.jpg |
| `hiper_real` | Tourbillon | Bugatti Veyron 16.4 - Seitenansicht, 5. April 2012, Duesseldorf.jpg |
