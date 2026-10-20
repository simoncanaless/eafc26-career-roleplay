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
    # Aston Martin: lo que se configura en configurator.astonmartin.com (revisado el 2026-10-20). Cada uno va al
    # configurador de su familia (la version se elige adentro). La web no da precios: aproximados en libras
    # (DB12 Volante y S Volante, DBX S y Valen de la prensa; el resto, de lanzamiento)
    Modelo("aston_vantage", "Aston Martin", "Vantage Coupe", "gt_aston", 165_000, 28,
           url_configurador="https://configurator.astonmartin.com/CL/model-select/M210/AM662"),
    Modelo("aston_vantage_roadster", "Aston Martin", "Vantage Roadster", "gt_aston", 180_000, 28,
           url_configurador="https://configurator.astonmartin.com/CL/model-select/M210/AM662"),
    Modelo("aston_vantage_s", "Aston Martin", "Vantage S Coupe", "gt_aston", 195_000, 35,
           url_configurador="https://configurator.astonmartin.com/CL/model-select/M210/AM662"),
    Modelo("aston_vantage_s_roadster", "Aston Martin", "Vantage S Roadster", "gt_aston", 210_000, 35,
           url_configurador="https://configurator.astonmartin.com/CL/model-select/M210/AM662"),
    Modelo("aston_db12", "Aston Martin", "DB12 Coupe", "gt_aston", 185_000, 28,
           url_configurador="https://configurator.astonmartin.com/CL/model-select/M200/AM578"),
    Modelo("aston_db12_volante", "Aston Martin", "DB12 Volante", "gt_aston", 199_500, 28,
           url_configurador="https://configurator.astonmartin.com/CL/model-select/M200/AM578"),
    Modelo("aston_db12_s", "Aston Martin", "DB12 S Coupe", "gt_aston", 208_000, 35,
           url_configurador="https://configurator.astonmartin.com/CL/model-select/M200/AM578"),
    Modelo("aston_db12_s_volante", "Aston Martin", "DB12 S Volante", "gt_aston", 224_000, 35,
           url_configurador="https://configurator.astonmartin.com/CL/model-select/M200/AM578"),
    Modelo("aston_dbx_gt", "Aston Martin", "DBX GT", "suv_deportivo", 180_000, 28,
           url_configurador="https://configurator.astonmartin.com/CL/model-select/M230/AM810"),
    Modelo("aston_dbx_s", "Aston Martin", "DBX S", "suv_deportivo", 210_000, 35,
           url_configurador="https://configurator.astonmartin.com/CL/model-select/M230/AM810"),
    Modelo("aston_dbx707", "Aston Martin", "DBX707", "suv_deportivo", 190_000, 28,
           url_configurador="https://configurator.astonmartin.com/CL/model-select/M230/AM810"),
    Modelo("aston_vanquish", "Aston Martin", "Vanquish Coupe", "gt_aston", 330_000, 42,
           url_configurador="https://configurator.astonmartin.com/CL/model-select/M222/AM374"),
    Modelo("aston_vanquish_volante", "Aston Martin", "Vanquish Volante", "gt_aston", 345_000, 42,
           url_configurador="https://configurator.astonmartin.com/CL/model-select/M222/AM374"),
    Modelo("aston_valhalla", "Aston Martin", "Valhalla", "hiper_real", 850_000, 120, aleron=True,
           url_configurador="https://configurator.astonmartin.com/CL/model-select/M255/AM003A"),
    Modelo("aston_valen", "Aston Martin", "Valen", "gt_aston", 1_500_000, 150,
           url_configurador="https://configurator.astonmartin.com/CL/model-select/M224/AM390"),
    Modelo("range_rover", "Range Rover", "Range Rover", "suv_lujo_real", 110_000, 14,
           url_configurador="https://www.rangerover.com/lr/en_xi/l460/ipr/personalise/"),
    Modelo("bugatti_tourbillon", "Bugatti", "Tourbillon", "hiper_real", 3_200_000, 90,
           url_configurador="https://www.bugatti.com/models/tourbillon"),
    # lo que faltaba de cada marca (revisado en sus configuradores el 2026-10-20). Precios aproximados en
    # libras (las webs no los dan): el Torcal (173.300) y el Luce (~550.000 euros) de la prensa
    Modelo("ferrari_296_gts", "Ferrari", "296 GTS", "ferrari_super", 278_000, 28,
           url_configurador="https://carconfigurator.ferrari.com/en_EN/ferrari_car_configurator/296gts"),
    Modelo("ferrari_296_speciale", "Ferrari", "296 Speciale", "ferrari_super", 365_000, 42,
           url_configurador="https://carconfigurator.ferrari.com/en_EN/ferrari_car_configurator/296speciale/default"),
    Modelo("ferrari_296_speciale_a", "Ferrari", "296 Speciale A", "ferrari_super", 410_000, 42,
           url_configurador="https://carconfigurator.ferrari.com/en_EN/ferrari_car_configurator/296speciale-a/default"),
    Modelo("ferrari_12cilindri_spider", "Ferrari", "12Cilindri Spider", "gt_ferrari", 375_000, 35,
           url_configurador="https://carconfigurator.ferrari.com/en_EN/ferrari_car_configurator/12cilindrispider/default"),
    Modelo("ferrari_849_spider", "Ferrari", "849 Testarossa Spider", "ferrari_super", 460_000, 42,
           url_configurador="https://carconfigurator.ferrari.com/en_EN/ferrari_car_configurator/849testarossaspider/default"),
    Modelo("ferrari_amalfi_spider", "Ferrari", "Amalfi Spider", "gt_ferrari", 215_000, 28,
           url_configurador="https://carconfigurator.ferrari.com/en_EN/ferrari_car_configurator/amalfispider/default"),
    Modelo("ferrari_luce", "Ferrari", "Luce", "suv_deportivo", 470_000, 60,
           url_configurador="https://carconfigurator.ferrari.com/en_EN/ferrari_car_configurator/luce/default"),
    Modelo("porsche_911_t", "Porsche", "911 Carrera T", "911_real", 108_000, 14,
           url_configurador="https://configurator.porsche.com/en-WW/mode/model/992182"),
    Modelo("porsche_911_s", "Porsche", "911 Carrera S", "911_real", 116_000, 14,
           url_configurador="https://configurator.porsche.com/en-WW/mode/model/9921S2"),
    Modelo("porsche_911_gts", "Porsche", "911 Carrera GTS", "911_real", 140_000, 21,
           url_configurador="https://configurator.porsche.com/en-WW/mode/model/992142"),
    Modelo("porsche_911_4s_cabrio", "Porsche", "911 Carrera 4S Cabriolet", "911_real", 128_000, 21,
           url_configurador="https://configurator.porsche.com/en-WW/mode/model/9926S2"),
    Modelo("porsche_911_targa", "Porsche", "911 Targa 4S", "911_real", 127_000, 21,
           url_configurador="https://configurator.porsche.com/en-WW/mode/model/9925S2"),
    Modelo("porsche_911_gt3", "Porsche", "911 GT3", "911_real", 155_000, 28,
           url_configurador="https://configurator.porsche.com/en-WW/mode/model/992812"),
    Modelo("porsche_911_turbo_cabrio", "Porsche", "911 Turbo S Cabriolet", "911_real", 205_000, 21,
           url_configurador="https://configurator.porsche.com/en-WW/mode/model/992652"),
    Modelo("porsche_taycan_base", "Porsche", "Taycan", "sedan_real", 87_000, 14,
           url_configurador="https://configurator.porsche.com/en-WW/mode/model/Y1AAI1"),
    Modelo("porsche_taycan_gt", "Porsche", "Taycan Turbo GT", "sedan_real", 190_000, 28,
           url_configurador="https://configurator.porsche.com/en-WW/mode/model/Y1AFT1"),
    Modelo("porsche_panamera", "Porsche", "Panamera 4 E-Hybrid", "sedan_real", 100_000, 14,
           url_configurador="https://configurator.porsche.com/en-WW/mode/model/YAABE1"),
    Modelo("porsche_panamera_turbo", "Porsche", "Panamera Turbo S E-Hybrid", "sedan_real", 190_000, 21,
           url_configurador="https://configurator.porsche.com/en-WW/mode/model/YAAFH1"),
    Modelo("porsche_macan", "Porsche", "Macan Electric", "suv_deportivo", 70_000, 14,
           url_configurador="https://configurator.porsche.com/en-WW/mode/model/XABAA1"),
    Modelo("porsche_macan_turbo", "Porsche", "Macan Turbo Electric", "suv_deportivo", 97_000, 14,
           url_configurador="https://configurator.porsche.com/en-WW/mode/model/XABFD1"),
    Modelo("porsche_macan_gts", "Porsche", "Macan GTS", "suv_deportivo", 85_000, 14,
           url_configurador="https://configurator.porsche.com/en-WW/mode/model/95BBW1"),
    Modelo("porsche_cayenne_coupe", "Porsche", "Cayenne Coupe", "suv_deportivo", 85_000, 14,
           url_configurador="https://configurator.porsche.com/en-WW/mode/model/9YBAI1"),
    Modelo("porsche_cayenne_turbo", "Porsche", "Cayenne Turbo E-Hybrid", "suv_deportivo", 155_000, 21,
           url_configurador="https://configurator.porsche.com/en-WW/mode/model/9YACT1"),
    Modelo("porsche_cayenne_electric", "Porsche", "Cayenne Electric", "suv_deportivo", 90_000, 14,
           url_configurador="https://configurator.porsche.com/en-WW/mode/model/X1AAA1"),
    Modelo("porsche_cayenne_turbo_electric", "Porsche", "Cayenne Turbo Electric", "suv_deportivo", 140_000, 21,
           url_configurador="https://configurator.porsche.com/en-WW/mode/model/X1ACD1"),
    Modelo("mclaren_gts", "McLaren", "GTS", "super_real", 165_000, 21,
           url_configurador="https://configurator.mclaren.com/model/gts"),
    Modelo("mclaren_artura_spider", "McLaren", "Artura Spider", "super_real", 215_000, 28,
           url_configurador="https://configurator.mclaren.com/model/artura-spider"),
    Modelo("mclaren_750s_spider", "McLaren", "750S Spider", "super_real", 265_000, 28,
           url_configurador="https://configurator.mclaren.com/model/750s-spider"),
    Modelo("amg_sl63", "Mercedes-AMG", "SL 63", "gt_lujo", 175_000, 21,
           url_configurador="https://www.mercedes-benz.co.uk/passengercars/mercedes-benz-cars/car-configurator.html/start/CCci/GB/en/tc/C590?subBrand=Mercedes-AMG"),
    Modelo("amg_gt_4puertas", "Mercedes-AMG", "GT 4-Door Coupe Electric", "sedan_real", 160_000, 21,
           url_configurador="https://www.mercedes-benz.co.uk/passengercars/mercedes-benz-cars/car-configurator.html/start/CCci/GB/en/tc/C590?subBrand=Mercedes-AMG"),
    Modelo("rolls_ghost", "Rolls-Royce", "Ghost", "gt_rolls", 280_000, 42,
           url_configurador="https://www.rolls-roycemotorcars.com/en_GB/bespoke/configure-your-rolls-royce.html"),
    Modelo("rolls_phantom", "Rolls-Royce", "Phantom", "gt_rolls", 460_000, 60,
           url_configurador="https://www.rolls-roycemotorcars.com/en_GB/bespoke/configure-your-rolls-royce.html"),
    Modelo("bentley_gtc", "Bentley", "Continental GTC", "gt_lujo", 215_000, 28,
           url_configurador="https://www.bentleymotors.com/en/misc/car-configurator.html/select/continental_gtc/continental_gtc"),
    Modelo("bentley_supersports", "Bentley", "Supersports", "gt_lujo", 300_000, 42,
           url_configurador="https://www.bentleymotors.com/en/misc/car-configurator.html"),
    Modelo("bentley_flying_spur", "Bentley", "Flying Spur", "sedan_real", 210_000, 28,
           url_configurador="https://www.bentleymotors.com/en/misc/car-configurator.html"),
    Modelo("bentley_bentayga", "Bentley", "Bentayga", "suv_lujo_real", 190_000, 28,
           url_configurador="https://www.bentleymotors.com/en/misc/car-configurator.html/select/bentayga/bentayga"),
    Modelo("bentley_bentayga_ewb", "Bentley", "Bentayga EWB", "suv_lujo_real", 230_000, 35,
           url_configurador="https://www.bentleymotors.com/en/misc/car-configurator.html"),
    Modelo("bentley_torcal", "Bentley", "Torcal", "suv_lujo_real", 173_300, 42,
           url_configurador="https://www.bentleymotors.com/en/misc/car-configurator.html"),
    Modelo("range_rover_sport", "Range Rover", "Range Rover Sport", "suv_lujo_real", 85_000, 14,
           url_configurador="https://www.rangerover.com/lr/en_xi/l461/ipr/personalise/"),
    Modelo("range_rover_velar", "Range Rover", "Range Rover Velar", "suv_deportivo", 55_000, 14,
           url_configurador="https://www.rangerover.com/lr/en_xi/l560/ipr/personalise/"),
    Modelo("range_rover_evoque", "Range Rover", "Range Rover Evoque", "suv_deportivo", 40_000, 14,
           url_configurador="https://www.rangerover.com/lr/en_xi/l551/ipr/personalise/"),
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
# agrupados por marca (en el orden en que aparece cada una), como los muestra el concesionario
MODELOS = [m for marca in dict.fromkeys(m.marca for m in MODELOS) for m in MODELOS if m.marca == marca]
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
