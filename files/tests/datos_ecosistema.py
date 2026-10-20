"""Datos de prueba chicos del ecosistema de Simon (famosas, paginas, periodistas,
futbolistas y autos de nicho) y ConEcosistema: una carpeta temporal con ellos
(EAFC_ECOSISTEMA) y un perfil guardado. Los usan test_ecosistema, test_amor,
test_instagram, test_autos, test_entrevista y test_economia."""

import json
import os
import tempfile
from pathlib import Path
from unittest import mock

import ayuda
from roleplay import database
from roleplay.models import PlayerProfile
from roleplay.servicios import ecosistema


def escribir_datos(carpeta: Path) -> Path:
    (carpeta / "famosas_ig.json").write_text(json.dumps({"celebridades": CELEBRIDADES}), encoding="utf-8")
    (carpeta / "ecosistema_ig.json").write_text(json.dumps(ECOSISTEMA), encoding="utf-8")
    (carpeta / "autos_marketplace.json").write_text(json.dumps({"autos_nicho": AUTOS}), encoding="utf-8")
    return carpeta


CELEBRIDADES = [
    {"nombre": "Estrella Mundial", "usuario_ig": "@estrella", "oficio": "cantante global", "categoria": "cantante",
     "anio_nacimiento": 1995, "exigencia": 95},
    {"nombre": "Actriz Conocida", "usuario_ig": "@actriz", "oficio": "actriz de series", "categoria": "actriz",
     "anio_nacimiento": 1998, "exigencia": 60},
    {"nombre": "Influencer Local", "usuario_ig": "@influ", "oficio": "influencer", "categoria": "influencer",
     "anio_nacimiento": 2001, "exigencia": 20},
]
ECOSISTEMA = {
    "paginas_futbol": [{"nombre": "433", "usuario_ig": "@433", "tipo": "viral"},
                       {"nombre": "Mercado", "usuario_ig": "@mercado", "tipo": "mercado"},
                       {"nombre": "Chismes", "usuario_ig": "@chismes", "tipo": "farandula"}],
    "periodistas": [{"nombre": f"Periodista {estilo} {i}", "usuario_ig": f"@p{estilo}{i}", "medio": f"Medio {i}",
                     "estilo": estilo} for estilo in ("mercado", "tactico", "polemico", "vestuario") for i in range(2)]
                   + [{"nombre": "Periodista emocional", "usuario_ig": "@pemocional", "medio": "Radio", "estilo": "emocional"}],
    "futbolistas_ig": [{"nombre": "Colega Top", "usuario_ig": "@colega", "rol": "futbolista",
                        "fama_minima_para_comentar": 35}],
}
AUTOS = [{"marca": "Marca", "modelo": f"Modelo {i}", "anio": 1995 + i, "categoria": "JDM Culto",
          "precio_base": 40_000 + 1_000 * i, "rareza": ("Extrema", "Alta", "Media")[i % 3], "nota": "",
          "imagen_local": ""} for i in range(15)]


class ConEcosistema(ayuda.PruebaConBase):
    def setUp(self):
        super().setUp()
        carpeta = Path(tempfile.mkdtemp(prefix="eafc_eco_"))
        (carpeta / "famosas_ig.json").write_text(json.dumps({"celebridades": CELEBRIDADES}), encoding="utf-8")
        (carpeta / "ecosistema_ig.json").write_text(json.dumps(ECOSISTEMA), encoding="utf-8")
        (carpeta / "autos_marketplace.json").write_text(json.dumps({"autos_nicho": AUTOS}), encoding="utf-8")
        parche = mock.patch.dict(os.environ, {"EAFC_ECOSISTEMA": str(carpeta)})
        parche.start()
        self.addCleanup(parche.stop)
        ecosistema._leer.cache_clear()
        self.addCleanup(ecosistema._leer.cache_clear)
        self.perfil = PlayerProfile(nombre_jugador="Simon Canales", club_actual="Man Utd")
        self.perfil.id = database.save_profile(self.perfil)
