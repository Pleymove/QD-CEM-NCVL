"""Moteur d'analyse : GC souterrains « travaux faits » sans câble tiré.

Règle métier (cf. brief « Extension GC souterrain ») :

1. ne retenir que les artères GC dont les travaux sont faits (par défaut
   ``suivi_pilotage`` ∈ {TRX fini, facturation}) ;
2. rattacher spatialement les câbles dont la géométrie intersecte la ligne GC
   (ou passe dans un buffer paramétrable autour), en CRS métrique EPSG:2154 ;
3. sortir le GC si AUCUN câble rattaché n'a un statut « tiré ».

Module indépendant de QGIS (travaille sur des objets ``GcArtere`` / ``Cable``
dont les géométries sont déjà en CRS métrique), donc testable hors QGIS.
"""

from .normalize import normalize_status, normalized_status_set
from .geometry import (
    bbox_of_lines, multiline_multiline_distance, SpatialGrid,
)

# Buffer par défaut : faible, car le rattachement GC↔câble repose d'abord sur
# l'intersection des lignes (distance 0), avec une tolérance configurable.
DEFAULT_GC_BUFFER_M = 1.0

# États de suivi GC considérés comme « travaux faits » par défaut.
DEFAULT_GC_DONE_STATES = ["TRX fini", "facturation"]

MOTIF_NO_CABLE = "Aucun câble associé au GC"
MOTIF_NO_PULLED = "Aucun câble au statut tiré sur GC"
MODE_RATTACHEMENT = "Spatial"


def _join(values, sep=" ; "):
    seen = []
    for value in values:
        text = "" if value is None else str(value).strip()
        if text and text not in seen:
            seen.append(text)
    return sep.join(seen)


def analyze_gc(gcs, cables, pulled_statuses, buffer_m=DEFAULT_GC_BUFFER_M,
               selected_done_states=None, selected_territoires=None):
    """Analyse les GC et renvoie ``(rows, counters, cable_detail)``.

    Paramètres
    ----------
    gcs, cables : listes de :class:`~core.models.GcArtere` / :class:`Cable`
        Géométries déjà reprojetées en CRS métrique (EPSG:2154).
    pulled_statuses : libellés de statut câble considérés comme « tirés ».
    buffer_m : tolérance de rattachement autour de la ligne GC (m).
    selected_done_states : états de suivi GC à retenir (None => tous).
    selected_territoires : territoires / plaques à retenir (None/vide => tous).
    """
    pulled_norm = normalized_status_set(pulled_statuses)
    done_norm = None
    if selected_done_states is not None:
        done_norm = {normalize_status(s) for s in selected_done_states}
    territoires_norm = None
    if selected_territoires:
        territoires_norm = {normalize_status(t) for t in selected_territoires}

    # Index spatial des câbles par bounding box. Cellule volontairement large
    # (lignes potentiellement longues) pour limiter le nombre de cellules.
    cell = max(float(buffer_m), 100.0)
    grid = SpatialGrid(cell)
    cable_bboxes = []
    for idx, cable in enumerate(cables):
        bbox = bbox_of_lines(cable.lines)
        cable_bboxes.append(bbox)
        grid.insert(idx, bbox)

    counters = {
        "gc_total": len(gcs),
        "gc_selected": 0,
        "cables_total": len(cables),
        "gc_without_pulled": 0,
        "cable_status_distinct": len(
            {normalize_status(c.status) for c in cables}
        ),
    }

    rows = []
    cable_detail = []

    for gc in gcs:
        if done_norm is not None:
            if normalize_status(gc.state) not in done_norm:
                continue
        if territoires_norm is not None:
            if normalize_status(gc.attrs.get("territoire")) not in territoires_norm:
                continue
        counters["gc_selected"] += 1

        linked = []  # list of (cable, distance)
        gc_bbox = bbox_of_lines(gc.lines)
        if gc_bbox is not None:
            minx, miny, maxx, maxy = gc_bbox
            qbbox = (minx - buffer_m, miny - buffer_m,
                     maxx + buffer_m, maxy + buffer_m)
            for idx in grid.query(qbbox):
                cable = cables[idx]
                dist = multiline_multiline_distance(gc.lines, cable.lines)
                if dist <= buffer_m:
                    linked.append((cable, dist))

        statuses_source = [c.status for c, _ in linked]
        statuses_norm = {normalize_status(s) for s in statuses_source}
        if statuses_norm & pulled_norm:
            continue

        counters["gc_without_pulled"] += 1
        motif = MOTIF_NO_CABLE if not linked else MOTIF_NO_PULLED
        refs = [c.ref for c, _ in linked]
        a = gc.attrs
        rows.append({
            "id_gc": gc.id,
            "nom_gc": gc.label,
            "commune": a.get("commune", ""),
            "departement": a.get("departement", ""),
            "territoire": a.get("territoire", ""),
            "suivi_pilotage": gc.state,
            "longueur": a.get("longueur", ""),
            "nb_cables": len(linked),
            "etats_cables": _join(statuses_source),
            "cables_associes": _join(refs),
            "cables_non_tires": _join(statuses_source),
            "motif": motif,
            "rayon_buffer_m": buffer_m,
            "nb_cables_intersectes": len(linked),
            "mode_rattachement": MODE_RATTACHEMENT,
            # Clés techniques (non affichées / non exportées en XLSX).
            "_fid": gc.fid,
            "_lines": gc.lines,
        })

        for cable, dist in linked:
            ca = cable.attrs
            cable_detail.append({
                "id_gc": gc.id,
                "ref_cable": cable.ref,
                "statut_cable": cable.status,
                "tire": False,
                "distance_m": round(dist, 2),
                "commune": ca.get("commune", ""),
                "departement": ca.get("departement", ""),
                "territoire": ca.get("territoire", ""),
            })

    return rows, counters, cable_detail
