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
    bbox_of_lines, covered_length, multiline_length,
    multiline_multiline_distance, SpatialGrid,
)

# Buffer par défaut : faible, car le rattachement GC↔câble repose d'abord sur
# l'intersection des lignes (distance 0), avec une tolérance configurable.
DEFAULT_GC_BUFFER_M = 1.0

# États de suivi GC considérés comme « travaux faits » par défaut.
DEFAULT_GC_DONE_STATES = ["TRX fini", "facturation"]

# Seuil par défaut du linéaire restant sans optique (ml) au-delà duquel un GC
# ressort. Strictement supérieur au seuil => le GC sort.
DEFAULT_RESTE_SEUIL_ML = 50.0

# Motif unique de sortie pour la règle « reste optique » (v1.1.1).
MOTIF_RESTE = "Reste à faire en optique"

# Motifs hérités v1.1.0 (conservés pour référence ; non utilisés par la règle
# de sortie actuelle, qui repose sur le reste optique).
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
               selected_done_states=None, selected_territoires=None,
               seuil_reste_ml=DEFAULT_RESTE_SEUIL_ML):
    """Analyse les GC et renvoie ``(rows, counters, cable_detail)``.

    Règle (v1.1.1) : pour chaque GC « travaux faits », on calcule le linéaire
    restant sans optique ::

        ML restant optique = longueur GC totale - longueur couverte par câble tiré

    Le GC ressort (motif « Reste à faire en optique ») si ce reste est
    strictement supérieur à ``seuil_reste_ml``. La couverture n'est comptée que
    pour les câbles dont le statut est « tiré » ; les câbles non tirés ne
    couvrent pas optiquement le GC.

    Paramètres
    ----------
    gcs, cables : listes de :class:`~core.models.GcArtere` / :class:`Cable`
        Géométries déjà reprojetées en CRS métrique (EPSG:2154).
    pulled_statuses : libellés de statut câble considérés comme « tirés ».
    buffer_m : tolérance de rattachement / couverture autour de la ligne GC (m).
    selected_done_states : états de suivi GC à retenir (None => tous).
    selected_territoires : territoires / plaques à retenir (None/vide => tous).
    seuil_reste_ml : seuil (ml) du reste optique au-delà duquel le GC ressort.
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
        "gc_reste_optique": 0,
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
        non_tires = [c.status for c, _ in linked
                     if normalize_status(c.status) not in pulled_norm]

        # Longueur couverte par les seuls câbles « tirés » rattachés.
        pulled_cover = [c.lines for c, _ in linked
                        if normalize_status(c.status) in pulled_norm]
        total_len = multiline_length(gc.lines)
        covered = covered_length(gc.lines, pulled_cover, buffer_m)
        if covered > total_len:
            covered = total_len
        reste = total_len - covered

        if reste <= seuil_reste_ml:
            continue

        counters["gc_reste_optique"] += 1
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
            "longueur_gc_totale": round(total_len, 1),
            "longueur_couverte": round(covered, 1),
            "ml_restant_optique": round(reste, 1),
            "seuil_reste_optique": seuil_reste_ml,
            "nb_cables": len(linked),
            "etats_cables": _join(statuses_source),
            "cables_associes": _join(refs),
            "cables_non_tires": _join(non_tires),
            "motif": MOTIF_RESTE,
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
                "tire": normalize_status(cable.status) in pulled_norm,
                "distance_m": round(dist, 2),
                "commune": ca.get("commune", ""),
                "departement": ca.get("departement", ""),
                "territoire": ca.get("territoire", ""),
            })

    return rows, counters, cable_detail
