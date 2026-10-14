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
    carroceria: str  # deportivo | gt | suv (la silueta del dibujo)
    precio: int
    dias_entrega: int = 14  # dias del juego entre el pedido y la entrega

    @property
    def nombre_completo(self) -> str:
        return f"{self.marca} {self.nombre}"


MODELOS = [
    Modelo("ferrari_296", "Ferrari", "296 GTB", "deportivo", 245_000, 28),
    Modelo("ferrari_sf90", "Ferrari", "SF90 Stradale", "deportivo", 390_000, 35),
    Modelo("ferrari_roma", "Ferrari", "Roma", "gt", 170_000, 28),
    Modelo("ferrari_purosangue", "Ferrari", "Purosangue", "suv", 315_000, 35),
    Modelo("porsche_911", "Porsche", "911 Carrera", "deportivo", 95_000, 14),
    Modelo("porsche_911_turbo", "Porsche", "911 Turbo S", "deportivo", 190_000, 21),
    Modelo("porsche_gt3rs", "Porsche", "911 GT3 RS", "deportivo", 180_000, 28),
    Modelo("porsche_taycan", "Porsche", "Taycan Turbo S", "gt", 150_000, 14),
    Modelo("porsche_cayenne", "Porsche", "Cayenne", "suv", 80_000, 14),
    Modelo("lambo_huracan", "Lamborghini", "Huracan", "deportivo", 200_000, 28),
    Modelo("lambo_revuelto", "Lamborghini", "Revuelto", "deportivo", 480_000, 42),
    Modelo("lambo_urus", "Lamborghini", "Urus", "suv", 190_000, 21),
    Modelo("mclaren_750s", "McLaren", "750S", "deportivo", 240_000, 28),
    Modelo("mclaren_artura", "McLaren", "Artura", "deportivo", 190_000, 21),
    Modelo("amg_g63", "Mercedes-AMG", "G 63", "suv", 165_000, 21),
    Modelo("amg_gt", "Mercedes-AMG", "GT 63", "gt", 150_000, 14),
    Modelo("rolls_cullinan", "Rolls-Royce", "Cullinan", "suv", 300_000, 42),
    Modelo("rolls_spectre", "Rolls-Royce", "Spectre", "gt", 330_000, 42),
    Modelo("bentley_gt", "Bentley", "Continental GT", "gt", 200_000, 28),
    Modelo("aston_db12", "Aston Martin", "DB12", "gt", 190_000, 28),
    Modelo("range_rover", "Range Rover", "Range Rover", "suv", 110_000, 14),
    Modelo("bugatti_tourbillon", "Bugatti", "Tourbillon", "deportivo", 3_200_000, 90),
]
POR_ID = {m.id: m for m in MODELOS}
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
