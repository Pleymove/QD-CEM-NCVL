"""Modèles de données métier, indépendants de QGIS.

L'adaptateur QGIS (``qgis_adapter.py``) convertit les entités des couches en
``Pole`` / ``Cable`` après reprojection des géométries en EPSG:2154. Le moteur
d'analyse ne manipule ensuite que ces objets simples, ce qui le rend testable
sans QGIS.
"""

from dataclasses import dataclass, field


@dataclass
class Pole:
    """Poteau / support (géométrie ponctuelle)."""

    id: str
    state: str
    xy: tuple = None  # (x, y) en CRS métrique, ou None si géométrie absente
    attrs: dict = field(default_factory=dict)
    fid: object = None  # identifiant d'entité QGIS (pour zoom / export)


@dataclass
class Cable:
    """Câble (géométrie (Multi)LineString)."""

    ref: str
    status: str
    lines: list = field(default_factory=list)  # [[(x, y), ...], ...]
    attrs: dict = field(default_factory=dict)
