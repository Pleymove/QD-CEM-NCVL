"""Plugin QGIS CEM NCVL — Poteaux sans câble tiré.

Point d'entrée chargé par QGIS via ``classFactory``.
"""


def classFactory(iface):  # noqa: N802 (nom imposé par l'API QGIS)
    from .cem_ncvl_plugin import CemNcvlPlugin
    return CemNcvlPlugin(iface)
