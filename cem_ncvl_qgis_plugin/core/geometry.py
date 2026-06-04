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


def _orientation(ax, ay, bx, by, cx, cy):
    """Produit vectoriel (AB x AC) : signe = orientation du triplet."""
    return (bx - ax) * (cy - ay) - (by - ay) * (cx - ax)


def _on_segment(ax, ay, bx, by, cx, cy):
    """Vrai si C (colinéaire à AB) est dans la bbox du segment AB."""
    return (min(ax, bx) <= cx <= max(ax, bx) and
            min(ay, by) <= cy <= max(ay, by))


def segments_intersect(p1, p2, p3, p4):
    """Vrai si les segments [p1,p2] et [p3,p4] se croisent (ou se touchent)."""
    ax, ay = p1
    bx, by = p2
    cx, cy = p3
    dx, dy = p4
    d1 = _orientation(cx, cy, dx, dy, ax, ay)
    d2 = _orientation(cx, cy, dx, dy, bx, by)
    d3 = _orientation(ax, ay, bx, by, cx, cy)
    d4 = _orientation(ax, ay, bx, by, dx, dy)
    if (((d1 > 0) != (d2 > 0)) and ((d3 > 0) != (d4 > 0))
            and d1 != 0 and d2 != 0 and d3 != 0 and d4 != 0):
        return True
    if d1 == 0 and _on_segment(cx, cy, dx, dy, ax, ay):
        return True
    if d2 == 0 and _on_segment(cx, cy, dx, dy, bx, by):
        return True
    if d3 == 0 and _on_segment(ax, ay, bx, by, cx, cy):
        return True
    if d4 == 0 and _on_segment(ax, ay, bx, by, dx, dy):
        return True
    return False


def segment_segment_distance(p1, p2, p3, p4):
    """Distance minimale entre deux segments (0 s'ils se croisent)."""
    if segments_intersect(p1, p2, p3, p4):
        return 0.0
    return min(
        _distance_point_segment(p1[0], p1[1], p3[0], p3[1], p4[0], p4[1]),
        _distance_point_segment(p2[0], p2[1], p3[0], p3[1], p4[0], p4[1]),
        _distance_point_segment(p3[0], p3[1], p1[0], p1[1], p2[0], p2[1]),
        _distance_point_segment(p4[0], p4[1], p1[0], p1[1], p2[0], p2[1]),
    )


def polyline_polyline_distance(line_a, line_b):
    """Distance minimale entre deux polylignes [(x, y), ...]."""
    if not line_a or not line_b:
        return INF
    if len(line_a) == 1:
        return point_polyline_distance(line_a[0], line_b)
    if len(line_b) == 1:
        return point_polyline_distance(line_b[0], line_a)
    best = INF
    for i in range(len(line_a) - 1):
        for j in range(len(line_b) - 1):
            d = segment_segment_distance(
                line_a[i], line_a[i + 1], line_b[j], line_b[j + 1])
            if d < best:
                best = d
                if best == 0.0:
                    return 0.0
    return best


def multiline_multiline_distance(lines_a, lines_b):
    """Distance minimale entre deux (multi)polylignes (listes de polylignes)."""
    best = INF
    for line_a in lines_a:
        for line_b in lines_b:
            d = polyline_polyline_distance(line_a, line_b)
            if d < best:
                best = d
                if best == 0.0:
                    return 0.0
    return best


def polyline_length(line):
    """Longueur d'une polyligne [(x, y), ...] (CRS métrique)."""
    total = 0.0
    for i in range(len(line) - 1):
        ax, ay = line[i]
        bx, by = line[i + 1]
        total += math.hypot(bx - ax, by - ay)
    return total


def multiline_length(lines):
    """Longueur totale d'une (multi)polyligne (liste de polylignes)."""
    return sum(polyline_length(line) for line in lines)


def _min_distance_point_to_multis(point, multis):
    """Distance min d'un point à une liste de (multi)polylignes de couverture."""
    best = INF
    for lines in multis:
        d = point_multiline_distance(point, lines)
        if d < best:
            best = d
            if best == 0.0:
                return 0.0
    return best


# Pas d'échantillonnage (m) pour le calcul de la longueur couverte. Plus le pas
# est petit, plus le calcul est précis (et lent). 2 m est un bon compromis pour
# un seuil métier de l'ordre de 50 m.
COVER_SAMPLE_STEP_M = 2.0


def covered_length(gc_lines, cover_multis, buffer_m,
                   step=COVER_SAMPLE_STEP_M):
    """Longueur de ``gc_lines`` couverte (à <= ``buffer_m``) par ``cover_multis``.

    Approximation par **échantillonnage** : chaque segment du GC est découpé en
    sous-segments d'environ ``step`` mètres ; un sous-segment est compté couvert
    si son milieu est à <= ``buffer_m`` d'au moins une des géométries de
    couverture. Le test étant binaire par sous-segment, l'union est implicite :
    **pas de double comptage** si plusieurs câbles se superposent sur la même
    portion. Précision de l'ordre de ``step``.

    ``cover_multis`` est une liste de (multi)polylignes (une par câble couvrant).
    """
    if not cover_multis:
        return 0.0
    step = max(float(step), 1e-6)
    covered = 0.0
    for line in gc_lines:
        for i in range(len(line) - 1):
            ax, ay = line[i]
            bx, by = line[i + 1]
            seg_len = math.hypot(bx - ax, by - ay)
            if seg_len == 0.0:
                continue
            n = int(math.ceil(seg_len / step))
            if n < 1:
                n = 1
            sub = seg_len / n
            for k in range(n):
                t = (k + 0.5) / n
                px = ax + t * (bx - ax)
                py = ay + t * (by - ay)
                if _min_distance_point_to_multis((px, py),
                                                 cover_multis) <= buffer_m:
                    covered += sub
    return covered


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
