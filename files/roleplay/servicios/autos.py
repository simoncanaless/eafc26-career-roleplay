"""
El concesionario: autos de marcas reales (solo el nombre, como texto: ni
logos ni modelos de las marcas), configurables. Simon lo decidio asi porque
la app es para usar entre amigos.

Los precios base son aproximados (de la vida real, en la moneda del club)
y cada opcion suma un porcentaje. El dibujo del auto lo arma la app
(ui/configurador.py) con siluetas propias segun la carroceria.
"""

from dataclasses import dataclass, field

REDONDEO = 100
PATENTE_PERSONALIZADA = 25_000
LARGO_PATENTE = 8
MANTENIMIENTO_SEMANAL = 0.004  # del precio: seguro, garage, service
OSTENTOSO_DESDE = 150_000


@dataclass(frozen=True)
class Modelo:
    id: str
    marca: str
    nombre: str
    carroceria: str  # la familia del dibujo (ui/configurador.py:SILUETAS)
    precio: int
    dias_entrega: int = 14  # dias del juego entre el pedido y la entrega
    aleron: bool = False  # el dibujo lleva aleron trasero
    url_configurador: str = ""  # la web oficial donde se configura (ui/configurador.py la abre adentro de la app)

    @property
    def nombre_completo(self) -> str:
        return f"{self.marca} {self.nombre}"


# Las direcciones salen de los botones "Configure" de cada web oficial
# (revisadas el 2026-10-15). Cada marca redirige al pais del usuario.
# Donde la marca no tiene una por modelo va su configurador general: el SF90
# y el Roma ya no se venden (los reemplazaron el 849 Testarossa y el Amalfi),
# Lamborghini y Rolls-Royce eligen el modelo adentro, y Bugatti no tiene
# configurador publico (va la pagina del Tourbillon).
MODELOS = [
    Modelo("ferrari_296", "Ferrari", "296 GTB", "ferrari_super", 245_000, 28,
           url_configurador="https://carconfigurator.ferrari.com/en_EN/ferrari_car_configurator/296gtb"),
    # hiperautos de reserva (pedido de Simon, 2026-10-20; precios que el paso, en libras)
    Modelo("ferrari_f80", "Ferrari", "F80", "hiper_real", 3_735_000, 45,
           url_configurador="https://carconfigurator.ferrari.com/en_EN/ferrari_car_configurator/f80/default"),
    Modelo("ferrari_12cilindri", "Ferrari", "12Cilindri", "gt_ferrari", 340_000, 35,
           url_configurador="https://carconfigurator.ferrari.com/en_EN/ferrari_car_configurator/12cilindri/default"),
    Modelo("ferrari_amalfi", "Ferrari", "Amalfi", "gt_ferrari", 195_000, 28,
           url_configurador="https://carconfigurator.ferrari.com/en_EN/ferrari_car_configurator/amalfi/default"),
    Modelo("ferrari_849", "Ferrari", "849 Testarossa", "ferrari_super", 420_000, 42,
           url_configurador="https://carconfigurator.ferrari.com/en_EN/ferrari_car_configurator/849testarossa/default"),
    Modelo("ferrari_purosangue", "Ferrari", "Purosangue", "suv_deportivo", 315_000, 35,
           url_configurador="https://carconfigurator.ferrari.com/en_EN/ferrari_car_configurator/purosangue"),
    # el Mission X es un prototipo de Porsche: Simon lo quiere igual, como reserva con su precio
    Modelo("porsche_mission_x", "Porsche", "Mission X", "hiper_real", 2_800_000, 60,
           url_configurador="https://configurator.porsche.com/en-WW/"),
    Modelo("porsche_911", "Porsche", "911 Carrera", "911_real", 95_000, 14,
           url_configurador="https://configurator.porsche.com/en-WW/mode/model/9921B2"),
    Modelo("porsche_911_turbo", "Porsche", "911 Turbo S", "911_real", 190_000, 21,
           url_configurador="https://configurator.porsche.com/en-WW/mode/model/992452"),
    # (el 911 GT3 RS 992.1 ya no esta en el configurador; el 2026-10-20 esta el GT3 S/C)
    Modelo("porsche_gt3_sc", "Porsche", "911 GT3 S/C", "911_real", 205_000, 28,
           url_configurador="https://configurator.porsche.com/en-WW/mode/model/992892"),
    Modelo("porsche_taycan", "Porsche", "Taycan Turbo S", "sedan_real", 150_000, 14,
           url_configurador="https://configurator.porsche.com/en-WW/mode/model/Y1AFM1"),
    Modelo("porsche_cayenne", "Porsche", "Cayenne", "suv_deportivo", 80_000, 14,
           url_configurador="https://configurator.porsche.com/en-WW/mode/model/9YAAI1"),
    # (revisado en las webs el 2026-10-20: el Huracan ya no se vende, lo reemplazo el Temerario)
    Modelo("lambo_temerario", "Lamborghini", "Temerario", "huracan", 265_000, 35,
           url_configurador="https://configurator.lamborghini.com/configurator/model/32007-20111/MBV-20007-2027"),
    Modelo("lambo_revuelto", "Lamborghini", "Revuelto", "cuna_real", 480_000, 42,
           url_configurador="https://configurator.lamborghini.com/configurator/model/32006-20111/MBV-21717-2027"),
    Modelo("lambo_urus", "Lamborghini", "Urus SE", "suv_deportivo", 190_000, 21,
           url_configurador="https://configurator.lamborghini.com/configurator/model/32005-20111/MBV-24727-2027"),
    Modelo("mclaren_w1", "McLaren", "W1", "hiper_real", 2_100_000, 42,
           url_configurador="https://www.mclaren.com/cars/gl_en/w1"),
    Modelo("mclaren_750s", "McLaren", "750S", "super_real", 240_000, 28,
           url_configurador="https://configurator.mclaren.com/mclaren-ui/?model/750s"),
    Modelo("mclaren_artura", "McLaren", "Artura", "super_real", 190_000, 21,
           url_configurador="https://configurator.mclaren.com/mclaren-ui/?model/artura"),
    Modelo("amg_g63", "Mercedes-AMG", "G 63", "g_real", 165_000, 21,
           url_configurador="https://www.mercedes-benz.co.uk/passengercars/mercedes-benz-cars/car-configurator.html/motorization/CCci/GB/en/bm/4632762"),
    Modelo("amg_gt", "Mercedes-AMG", "GT 63 Coupe", "gt_lujo", 150_000, 14,
           url_configurador="https://www.mercedes-benz.co.uk/passengercars/mercedes-benz-cars/car-configurator.html/start/CCci/GB/en/tc/C590?subBrand=Mercedes-AMG"),
    Modelo("rolls_cullinan", "Rolls-Royce", "Cullinan", "suv_lujo_real", 300_000, 42,
           url_configurador="https://www.rolls-roycemotorcars.com/en_GB/bespoke/configure-your-rolls-royce.html"),
    Modelo("rolls_spectre", "Rolls-Royce", "Spectre", "gt_rolls", 330_000, 42,
           url_configurador="https://www.rolls-roycemotorcars.com/en_GB/bespoke/configure-your-rolls-royce.html"),
    Modelo("bentley_gt", "Bentley", "Continental GT", "gt_lujo", 200_000, 28,
           url_configurador="https://www.bentleymotors.com/en/misc/car-configurator.html/select/continental_gt/continental_gt"),
    Modelo("aston_db12", "Aston Martin", "DB12", "gt_aston", 190_000, 28,
           url_configurador="https://configurator.astonmartin.com/INT/configuration/AM576"),
    Modelo("range_rover", "Range Rover", "Range Rover", "suv_lujo_real", 110_000, 14,
           url_configurador="https://www.rangerover.com/lr/en_xi/l460/ipr/personalise/"),
    Modelo("bugatti_tourbillon", "Bugatti", "Tourbillon", "hiper_real", 3_200_000, 90,
           url_configurador="https://www.bugatti.com/models/tourbillon"),
]
# ya no se venden (el SF90 y el Roma los reemplazaron Ferrari), pero si alguien los
# pidio siguen en su garage
DESCONTINUADOS = [
    Modelo("lambo_huracan", "Lamborghini", "Huracan", "huracan", 200_000, 28,
           url_configurador="https://configurator.lamborghini.com/configurator/"),
    Modelo("porsche_gt3rs", "Porsche", "911 GT3 RS", "911_real", 180_000, 28, aleron=True,
           url_configurador="https://configurator.porsche.com/en-WW/mode/model/992850"),
    Modelo("ferrari_sf90", "Ferrari", "SF90 Stradale", "ferrari_super", 390_000, 35,
           url_configurador="https://carconfigurator.ferrari.com/en_EN"),
    Modelo("ferrari_roma", "Ferrari", "Roma", "gt_ferrari", 170_000, 28,
           url_configurador="https://carconfigurator.ferrari.com/en_EN"),
]
POR_ID = {m.id: m for m in MODELOS + DESCONTINUADOS}
MARCAS = list(dict.fromkeys(m.marca for m in MODELOS))


@dataclass(frozen=True)
class Opcion:
    id: str
    nombre: str
    recargo: float = 0.0  # del precio base
    color: str = ""  # para el dibujo


# pintura: el color no cambia el precio; el acabado si
COLORES = [
    Opcion("rojo", "Rojo", color="#C8102E"),
    Opcion("amarillo", "Amarillo", color="#F4C300"),
    Opcion("naranja", "Naranja", color="#F26B1D"),
    Opcion("verde", "Verde", color="#1E7B45"),
    Opcion("azul", "Azul", color="#1F4FA8"),
    Opcion("celeste", "Celeste", color="#4FA6D9"),
    Opcion("negro", "Negro", color="#15171A"),
    Opcion("gris", "Gris", color="#8A8F94"),
    Opcion("blanco", "Blanco", color="#ECEDEF"),
    Opcion("violeta", "Violeta", color="#5B2C8F"),
]
ACABADOS = [
    Opcion("brillante", "Brillante"),
    Opcion("metalizado", "Metalizado", 0.02),
    Opcion("mate", "Mate", 0.06),
]
LLANTAS = [
    Opcion("estandar", "Estandar", color="#C7CBD1"),
    Opcion("deportivas", "Deportivas", 0.015, "#D9DCE0"),
    Opcion("forjadas", "Forjadas negras", 0.03, "#1C1D20"),
    Opcion("doradas", "Doradas", 0.04, "#C9A227"),
]
PINZAS = [
    Opcion("negras", "Negras", color="#202124"),
    Opcion("rojas", "Rojas", 0.005, "#D0102B"),
    Opcion("amarillas", "Amarillas", 0.005, "#F2C200"),
    Opcion("verdes", "Verdes", 0.005, "#1FB55C"),
]
FRANJAS = [
    Opcion("ninguna", "Sin franja"),
    Opcion("lateral", "Lateral", 0.01),
    Opcion("doble", "Doble lateral", 0.015),
]
INTERIORES = [
    Opcion("negro", "Cuero negro"),
    Opcion("tostado", "Cuero tostado", 0.02),
    Opcion("rojo", "Cuero rojo", 0.02),
    Opcion("blanco", "Cuero blanco", 0.02),
]
EXTRAS = [
    Opcion("carbono", "Paquete de fibra de carbono", 0.08),
    Opcion("escape", "Escape deportivo", 0.03),
]
GRUPOS = {
    "color": COLORES, "acabado": ACABADOS, "llantas": LLANTAS, "pinzas": PINZAS,
    "franja": FRANJAS, "interior": INTERIORES,
}


def opcion(grupo: str, opcion_id: str) -> Opcion:
    lista = EXTRAS if grupo == "extras" else GRUPOS[grupo]
    return next(o for o in lista if o.id == opcion_id)


@dataclass
class Configuracion:
    modelo: str
    color: str = "rojo"
    acabado: str = "brillante"
    llantas: str = "estandar"
    pinzas: str = "negras"
    franja: str = "ninguna"
    color_franja: str = "negro"
    interior: str = "negro"
    extras: list = field(default_factory=list)
    patente: str = ""

    def a_dict(self) -> dict:
        return dict(self.__dict__, extras=list(self.extras))

    @classmethod
    def desde_dict(cls, datos: dict) -> "Configuracion":
        return cls(**{k: v for k, v in datos.items() if k in cls.__dataclass_fields__})


def limpiar_patente(texto: str) -> str:
    """Letras, numeros y espacios, en mayuscula y hasta LARGO_PATENTE."""
    return "".join(c for c in texto.upper() if c.isalnum() or c == " ").strip()[:LARGO_PATENTE]


def precio(config: Configuracion) -> int:
    modelo = POR_ID[config.modelo]
    recargo = sum(
        opcion(grupo, getattr(config, grupo)).recargo for grupo in ("acabado", "llantas", "pinzas", "franja", "interior")
    ) + sum(opcion("extras", e).recargo for e in config.extras)
    total = modelo.precio * (1 + recargo) + (PATENTE_PERSONALIZADA if config.patente else 0)
    return int(round(total / REDONDEO) * REDONDEO)


def describir(config: Configuracion) -> str:
    """"rojo metalizado, llantas forjadas negras, pinzas amarillas, ..." para
    la pantalla, la prensa y los hinchas."""
    partes = [f"{opcion('color', config.color).nombre.lower()} {opcion('acabado', config.acabado).nombre.lower()}"]
    if config.llantas != "estandar":
        partes.append(f"llantas {opcion('llantas', config.llantas).nombre.lower()}")
    if config.pinzas != "negras":
        partes.append(f"pinzas {opcion('pinzas', config.pinzas).nombre.lower()}")
    if config.franja != "ninguna":
        partes.append(f"franja {opcion('franja', config.franja).nombre.lower()} {opcion('color', config.color_franja).nombre.lower()}")
    if config.interior != "negro":
        partes.append(f"interior de {opcion('interior', config.interior).nombre.lower()}")
    partes += [opcion("extras", e).nombre.lower() for e in config.extras]
    if config.patente:
        partes.append(f"patente \"{config.patente}\"")
    return ", ".join(partes)


def primera_mayuscula(texto: str) -> str:
    """Como str.capitalize(), sin pasar el resto a minuscula (la patente)."""
    return texto[:1].upper() + texto[1:]


def mantenimiento(precio_total: int) -> int:
    return round(precio_total * MANTENIMIENTO_SEMANAL)
