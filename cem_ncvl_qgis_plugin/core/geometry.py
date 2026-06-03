"""Helpers géométriques purs (sans dépendance QGIS).

Toutes les coordonnées sont supposées exprimées dans un CRS métrique
(EPSG:2154 dans l'usage du plugin). Le module fournit :

- le calcul de distance point -> polyligne / multi-polyligne ;
- une grille spatiale légère pour pré-filtrer les candidats avant le calcul
  précis de distance, afin d'éviter un coût O(n*m) sur de gros jeux.

Cette logique est partagée entre l'adaptateur QGIS (après reprojection des
géométries en EPSG:2154) et les tests unitaires, ce qui garantit que le
rattachement spatial testé est exactement celui exécuté en production.
"""

import math

INF = float("inf")


def _distance_point_segment(px, py, ax, ay, bx, by):
    """Distance euclidienne entre un point et un segment [A, B]."""
    dx = bx - ax
    dy = by - ay
    if dx == 0.0 and dy == 0.0:
        return math.hypot(px - ax, py - ay)
    t = ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy)
    if t < 0.0:
        t = 0.0
    elif t > 1.0:
        t = 1.0
    cx = ax + t * dx
    cy = ay + t * dy
    return math.hypot(px - cx, py - cy)


def point_polyline_distance(point, line):
    """Distance minimale entre un point (x, y) et une polyligne [(x, y), ...]."""
    if not line:
        return INF
    px, py = point
    if len(line) == 1:
        return math.hypot(px - line[0][0], py - line[0][1])
    best = INF
    for i in range(len(line) - 1):
        ax, ay = line[i]
        bx, by = line[i + 1]
        d = _distance_point_segment(px, py, ax, ay, bx, by)
        if d < best:
            best = d
    return best


def point_multiline_distance(point, lines):
    """Distance minimale entre un point et une liste de polylignes.

    ``lines`` modélise une (Multi)LineString : liste de polylignes, chaque
    polyligne étant une liste de couples (x, y).
    """
    best = INF
    for line in lines:
        d = point_polyline_distance(point, line)
        if d < best:
            best = d
    return best


def bbox_of_lines(lines):
    """Bounding box (minx, miny, maxx, maxy) d'une (multi)polyligne, ou None."""
    minx = miny = INF
    maxx = maxy = -INF
    found = False
    for line in lines:
        for x, y in line:
            found = True
            if x < minx:
                minx = x
            if y < miny:
                miny = y
            if x > maxx:
                maxx = x
            if y > maxy:
                maxy = y
    if not found:
        return None
    return (minx, miny, maxx, maxy)


class SpatialGrid:
    """Grille de hachage spatial pour pré-filtrer des candidats par bbox."""

    def __init__(self, cell_size):
        self.cell = max(float(cell_size), 1e-6)
        self.buckets = {}

    def _cells_for_bbox(self, bbox):
        minx, miny, maxx, maxy = bbox
        cx0 = int(math.floor(minx / self.cell))
        cx1 = int(math.floor(maxx / self.cell))
        cy0 = int(math.floor(miny / self.cell))
        cy1 = int(math.floor(maxy / self.cell))
        for cx in range(cx0, cx1 + 1):
            for cy in range(cy0, cy1 + 1):
                yield (cx, cy)

    def insert(self, item_id, bbox):
        if bbox is None:
            return
        for cell in self._cells_for_bbox(bbox):
            self.buckets.setdefault(cell, set()).add(item_id)

    def query(self, bbox):
        """Identifiants candidats dont la bbox recouvre potentiellement bbox."""
        result = set()
        for cell in self._cells_for_bbox(bbox):
            bucket = self.buckets.get(cell)
            if bucket:
                result.update(bucket)
        return result
