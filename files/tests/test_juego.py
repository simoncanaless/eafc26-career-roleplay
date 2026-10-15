import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import ayuda
from roleplay import ajustes, config
from roleplay.servicios import accesos, juego


def registro(valores: dict, subclaves: dict | None = None):
    """Registro de Windows falso: valores[(raiz, ruta, nombre)] y subclaves[(raiz, ruta)]."""
    leer = lambda raiz, ruta, nombre: valores.get((raiz, ruta, nombre))  # noqa: E731
    listar = lambda raiz, ruta: (subclaves or {}).get((raiz, ruta), [])  # noqa: E731
    return leer, listar


class ConCarpeta(unittest.TestCase):
    def setUp(self):
        temporal = tempfile.TemporaryDirectory()
        self.addCleanup(temporal.cleanup)
        self.dir = Path(temporal.name)


class TestDeteccion(ConCarpeta):
    def _steam(self, appid="3405690", nombre="EA SPORTS FC™ 26", en_otra_biblioteca=True):
        steam = self.dir / "Steam"
        biblioteca = self.dir / "SteamLibrary" if en_otra_biblioteca else steam
        (steam / "steamapps").mkdir(parents=True)
        (biblioteca / "steamapps" / "common" / "FC 26").mkdir(parents=True)
        (biblioteca / "steamapps" / "common" / "FC 26" / "FC26.exe").write_bytes(b"MZ")
        ruta_vdf = str(biblioteca).replace("\\", "\\\\")
        (steam / "steamapps" / "libraryfolders.vdf").write_text(
            f'"libraryfolders"\n{{\n "1"\n {{\n  "path"  "{ruta_vdf}"\n }}\n}}\n', encoding="utf-8"
        )
        (biblioteca / "steamapps" / f"appmanifest_{appid}.acf").write_text(
            f'"AppState"\n{{\n "appid" "{appid}"\n "name" "{nombre}"\n "installdir" "FC 26"\n}}\n', encoding="utf-8"
        )
        leer, _ = registro({("HKCU", r"Software\Valve\Steam", "SteamPath"): str(steam)})
        return leer, biblioteca

    def test_steam_en_otra_biblioteca(self):
        # como en el PC de Simon: Steam en C:, el juego en F:\SteamLibrary
        leer, biblioteca = self._steam()
        encontrado = juego.buscar_en_steam(leer)
        self.assertEqual(encontrado.comando, "steam://rungameid/3405690")
        self.assertEqual(encontrado.icono, str(biblioteca / "steamapps" / "common" / "FC 26" / "FC26.exe"))
        self.assertTrue(encontrado.es_url)

    def test_steam_reconoce_el_juego_por_el_nombre_si_cambia_el_appid(self):
        leer, _ = self._steam(appid="9999999", nombre="EA SPORTS FC 26 Ultimate")
        self.assertEqual(juego.buscar_en_steam(leer).comando, "steam://rungameid/9999999")

    def test_steam_sin_el_juego(self):
        leer, _ = self._steam(appid="570", nombre="Dota 2")
        self.assertIsNone(juego.buscar_en_steam(leer))
        self.assertIsNone(juego.buscar_en_steam(lambda *_: None))

    def test_ea_app(self):
        carpeta = self.dir / "EA Games" / "FC 26"
        carpeta.mkdir(parents=True)
        (carpeta / "FC26.exe").write_bytes(b"MZ")
        base = r"SOFTWARE\WOW6432Node\EA Games"
        leer, listar = registro(
            {("HKLM", base + r"\EA SPORTS FC 26", "Install Dir"): str(carpeta)},
            {("HKLM", base): ["Battlefield 2042", "EA SPORTS FC 26"]},
        )
        encontrado = juego.buscar_en_ea(leer, listar)
        self.assertEqual((encontrado.plataforma, encontrado.comando), ("ea", str(carpeta / "FC26.exe")))

    def test_epic(self):
        (self.dir / "x.item").write_text(
            json.dumps(
                {"DisplayName": "EA SPORTS FC 26", "CatalogNamespace": "ns", "CatalogItemId": "item",
                 "AppName": "app", "InstallLocation": str(self.dir), "LaunchExecutable": "FC26.exe"}
            ),
            encoding="utf-8",
        )
        encontrado = juego.buscar_en_epic(self.dir)
        self.assertEqual(
            encontrado.comando, "com.epicgames.launcher://apps/ns%3Aitem%3Aapp?action=launch&silent=true"
        )

    def test_lo_elegido_a_mano_manda_y_se_puede_olvidar(self):
        exe = self.dir / "FC26.exe"
        exe.write_bytes(b"MZ")
        with mock.patch.object(config, "ARCHIVO_AJUSTES", self.dir / "ajustes.json"), \
                mock.patch.object(juego, "detectar_juego", return_value=juego.Juego("steam", "steam://rungameid/1")):
            juego.elegir_a_mano(str(exe))
            self.assertEqual(juego.juego_configurado().comando, str(exe))
            juego.olvidar_eleccion()
            self.assertEqual(juego.juego_configurado().plataforma, "steam")
            with self.assertRaises(ValueError):
                juego.elegir_a_mano(str(self.dir / "no_existe.exe"))

    def test_abrir_usa_la_plataforma(self):
        with mock.patch.object(juego.os, "startfile", create=True) as abrir:
            juego.abrir_juego(juego.Juego("steam", "steam://rungameid/3405690"))
        abrir.assert_called_once_with("steam://rungameid/3405690")
        with self.assertRaises(RuntimeError):
            juego.abrir_juego(juego.Juego("manual", str(self.dir / "borrado.exe")))


class TestAccesos(ConCarpeta):
    def test_los_dos_iconos_de_verdad(self):
        """Crea los accesos en una carpeta temporal con el WScript.Shell real."""
        (self.dir / "EAFC 26 Roleplay.lnk").write_bytes(b"viejo")
        steam = juego.Juego("steam", "steam://rungameid/3405690", r"F:\juego\FC26.exe")
        creados = accesos.crear_accesos(steam, self.dir)

        self.assertEqual([r.name for r in creados], ["EA FC 26.url", "EA FC 26 + Roleplay.lnk"])
        self.assertEqual(
            (self.dir / "EA FC 26.url").read_bytes(),
            b"[InternetShortcut]\r\nURL=steam://rungameid/3405690\r\nIconFile=F:\\juego\\FC26.exe\r\nIconIndex=0\r\n",
        )
        self.assertFalse((self.dir / "EAFC 26 Roleplay.lnk").exists())

        lectura = ayuda.subprocess.run(
            ["powershell", "-NoProfile", "-Command",
             f"$a = (New-Object -ComObject WScript.Shell).CreateShortcut('{self.dir / 'EA FC 26 + Roleplay.lnk'}'); "
             "$a.TargetPath; $a.Arguments"],
            capture_output=True, text=True,
        ).stdout.splitlines()
        ejecutable, argumentos = accesos.lanzador_de_la_app()
        self.assertEqual(lectura[0].lower(), ejecutable.lower())
        self.assertTrue(lectura[1].endswith("--jugar"))

    def test_juego_elegido_a_mano_va_como_lnk(self):
        with mock.patch.object(accesos, "crear_lnk") as crear_lnk:
            accesos.crear_accesos(juego.Juego("manual", r"D:\Juegos\FC26.exe", r"D:\Juegos\FC26.exe"), self.dir)
        destinos = [llamada.args[1] for llamada in crear_lnk.call_args_list]
        self.assertEqual(destinos[0], r"D:\Juegos\FC26.exe")

    def test_sin_juego_solo_el_de_roleplay(self):
        with mock.patch.object(accesos, "crear_lnk") as crear_lnk:
            creados = accesos.crear_accesos(None, self.dir)
        self.assertEqual([r.name for r in creados], ["EA FC 26 + Roleplay.lnk"])
        self.assertEqual(crear_lnk.call_count, 1)

    def test_empaquetada_el_icono_apunta_al_propio_exe(self):
        with mock.patch.object(config, "EMPAQUETADA", True), \
                mock.patch.object(accesos.sys, "executable", r"C:\Amigo\EAFC Roleplay\EAFC Roleplay.exe"):
            self.assertEqual(accesos.lanzador_de_la_app(), (r"C:\Amigo\EAFC Roleplay\EAFC Roleplay.exe", ""))


class TestDatosDeCadaUno(ConCarpeta):
    def test_carpeta_de_datos(self):
        self.assertEqual(config.carpeta_datos({}, empaquetada=False), config.RAIZ_PROYECTO)
        self.assertEqual(
            config.carpeta_datos({"APPDATA": r"C:\Users\amigo\AppData\Roaming"}, empaquetada=True),
            Path(r"C:\Users\amigo\AppData\Roaming") / "EAFC26 Roleplay",
        )
        self.assertEqual(
            config.carpeta_datos({"EAFC_ROLEPLAY_DATOS": str(self.dir), "APPDATA": "x"}, empaquetada=True), self.dir
        )

    def test_ajustes_rotos_no_rompen_nada(self):
        archivo = self.dir / "ajustes.json"
        archivo.write_text("{esto no es json", encoding="utf-8")
        with mock.patch.object(config, "ARCHIVO_AJUSTES", archivo):
            self.assertEqual(ajustes.leer(), {})
            ajustes.guardar(en_vivo=True)
            self.assertEqual(ajustes.leer(), {"en_vivo": True})


class TestApp(ayuda.PruebaDeInterfaz):
    def test_jugar_abre_el_juego_y_la_sala_de_prensa(self):
        import app
        from roleplay.ui import ajustes as ui_ajustes
        from roleplay.ui.menu import MainMenuWindow

        steam = juego.Juego("steam", "steam://rungameid/3405690")
        with mock.patch.object(ui_ajustes, "juego_configurado", return_value=steam), \
                mock.patch.object(ui_ajustes, "abrir_juego") as abrir:
            self.assertTrue(ui_ajustes.abrir_juego_o_preguntar(None))
        abrir.assert_called_once_with(steam)
        ventana = app._crear_ventana("menu", jugar=True)
        self.assertEqual(ventana.stack.currentIndex(), MainMenuWindow.PAGINA_ENTREVISTAS)

    def test_sin_juego_se_puede_cancelar(self):
        from roleplay.ui import ajustes as ui_ajustes

        with mock.patch.object(ui_ajustes, "juego_configurado", return_value=None), \
                mock.patch.object(ui_ajustes.QFileDialog, "getOpenFileName", return_value=("", "")), \
                mock.patch.object(ui_ajustes, "abrir_juego") as abrir:
            self.assertFalse(ui_ajustes.abrir_juego_o_preguntar(None))
        abrir.assert_not_called()

    def test_no_se_pide_ninguna_clave(self):
        from roleplay.ui import ajustes as ui_ajustes

        self.assertFalse(hasattr(ui_ajustes, "DialogoClave"))
        self.assertFalse(hasattr(ui_ajustes, "pedir_clave_si_falta"))
        with self.assertRaises(ImportError):
            from roleplay import gemini  # noqa: F401

    def test_diagnostico(self):
        proceso = ayuda.correr_aislado(
            "import app, sys\n"
            "from unittest import mock\n"
            "from roleplay import diagnostico\n"
            "with mock.patch.object(diagnostico, 'revisar', return_value=[(True, 'todo bien')]):\n"
            "    sys.exit(app.main(['--diagnostico']))"
        )
        self.assertEqual(proceso.returncode, 0, proceso.stderr)
        self.assertIn("[OK] todo bien", proceso.stdout)


if __name__ == "__main__":
    unittest.main()
