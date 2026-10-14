"""Leer la partida guardada de la carrera de FC 26 (resultados, quien hizo
los goles, estadisticas). Solo se lee una COPIA del guardado: el juego no se
toca. Investigacion del formato: docs/partida-fc26.md.

    formato.py  bytes -> registros (bases de datos de EA y secciones de carrera)
    carrera.py  registros -> el mundo de la carrera (equipos, partidos, actuaciones)
    lector.py   encontrar el guardado mas reciente y leerlo (con cache)
"""
