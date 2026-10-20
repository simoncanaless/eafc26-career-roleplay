"""Todos los pop-ups con el diseno de la app: en espanol, el explorador de Qt y los calendarios."""

import unittest

import ayuda
from PySide6.QtCore import QDate, QEvent, Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QApplication, QDateEdit, QMessageBox

from roleplay.ui import estilos


class TestPopups(ayuda.PruebaDeInterfaz):
    def setUp(self):
        super().setUp()
        estilos.aplicar_estilo(QApplication.instance())

    def test_los_botones_de_los_popups_en_espanol(self):
        caja = QMessageBox(QMessageBox.Icon.Question, "x", "y",
                           QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        textos = {b.text().replace("&", "") for b in caja.buttons()}
        self.assertEqual(textos, {"Sí", "No"})
        caja.deleteLater()

    def test_el_explorador_de_archivos_con_el_tema(self):
        self.assertTrue(QApplication.instance().testAttribute(Qt.ApplicationAttribute.AA_DontUseNativeDialogs))

    def test_los_calendarios_sin_fines_de_semana_en_rojo(self):
        fecha = QDateEdit(QDate(2026, 10, 20))
        fecha.setCalendarPopup(True)
        fecha.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen)
        fecha.show()
        QApplication.processEvents()
        color = fecha.calendarWidget().weekdayTextFormat(Qt.DayOfWeek.Sunday).foreground().color()
        self.assertEqual(color, QColor(estilos.SECUNDARIO))
        fecha.deleteLater()

    def test_la_barra_oscura_no_falla_fuera_de_windows(self):
        caja = QMessageBox()
        estilos.barra_oscura(caja)  # offscreen: no hace nada, y no falla
        self.assertTrue(estilos._BarrasOscuras().eventFilter(caja, QEvent(QEvent.Type.Show)) is False)
        caja.deleteLater()

    def test_el_color_para_windows(self):
        self.assertEqual(estilos._colorref("#0A0E14"), 0x00140E0A)


if __name__ == "__main__":
    unittest.main()
