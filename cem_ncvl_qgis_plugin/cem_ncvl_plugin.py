"""Classe principale du plugin QGIS CEM NCVL.

Gère l'ajout de l'action dans le menu / la barre d'outils et l'ouverture de
la fenêtre d'analyse.
"""

import os

from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtWidgets import QAction

from .ui.main_dialog import CemNcvlDialog

PLUGIN_NAME = "CEM NCVL — Poteaux sans câble tiré"
ICON_PATH = os.path.join(os.path.dirname(__file__), "resources", "icon.svg")


class CemNcvlPlugin:
    """Plugin QGIS CEM NCVL."""

    def __init__(self, iface):
        self.iface = iface
        self.action = None
        self.dialog = None

    def initGui(self):  # noqa: N802 (API QGIS)
        icon = QIcon(ICON_PATH) if os.path.exists(ICON_PATH) else QIcon()
        self.action = QAction(icon, PLUGIN_NAME, self.iface.mainWindow())
        self.action.triggered.connect(self.run)
        self.iface.addToolBarIcon(self.action)
        self.iface.addPluginToMenu(PLUGIN_NAME, self.action)

    def unload(self):
        if self.action is not None:
            self.iface.removeToolBarIcon(self.action)
            self.iface.removePluginMenu(PLUGIN_NAME, self.action)
            self.action = None

    def run(self):
        # Recréer le dialogue garantit la prise en compte des couches ouvertes.
        self.dialog = CemNcvlDialog(self.iface, self.iface.mainWindow())
        self.dialog.show()
        self.dialog.raise_()
        self.dialog.activateWindow()
