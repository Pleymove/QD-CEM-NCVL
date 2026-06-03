"""Configuration pytest : rend le package du plugin importable.

Les tests ne portent que sur la logique métier (``core``), qui n'importe
jamais QGIS, et peuvent donc s'exécuter dans un Python standard.
"""

import os
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
