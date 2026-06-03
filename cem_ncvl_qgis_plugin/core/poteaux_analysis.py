"""Moteur d'analyse : poteaux remplacés / implantés sans câble tiré.

Règle métier (cf. spécification fonctionnelle CEM NCVL) :

1. ne retenir que les poteaux dont l'état correspond à la sélection
   (par défaut la famille ``plante`` = planté / remplacé / recalé) ;
2. rattacher spatialement les câbles dont la géométrie passe dans un buffer
   autour du poteau (rayon paramétrable, 5 m par défaut, CRS EPSG:2154) ;
3. sortir le poteau si AUCUN câble rattaché n'a un statut « tiré ».

Le module est volontairement indépendant de QGIS : il travaille sur des objets
``Pole`` / ``Cable`` dont les géométries sont déjà exprimées dans un CRS
métrique. Cela permet de tester la logique sans QGIS.
"""

from .normalize import normalize_status, normalized_status_set
from .geometry import bbox_of_lines, point_multiline_distance, SpatialGrid

DEFAULT_BUFFER_M = 5.0

MOTIF_NO_CABLE = "Aucun câble associé"
MOTIF_NO_PULLED = "Aucun câble au statut tiré"

MODE_RATTACHEMENT = "Spatial"

# Valeur d'état poteau retenue par défaut pour le cas client (famille QGIS
# planté / remplacé / recalé).
DEFAULT_POLE_STATES = ["plante"]


def _join(values, sep=" ; "):
    """Concatène des libellés lisibles en supprimant les vides et doublons."""
    seen = []
    for value in values:
        text = "" if value is None else str(value).strip()
        if text and text not in seen:
            seen.append(text)
    return sep.join(seen)


def analyze(poles, cables, pulled_statuses, buffer_m=DEFAULT_BUFFER_M,
            selected_pole_states=None, selected_territoires=None):
    """Analyse les poteaux et renvoie ``(rows, counters, cable_detail)``.

    Paramètres
    ----------
    poles, cables : listes de :class:`~core.models.Pole` / :class:`Cable`
        Géométries déjà reprojetées en CRS métrique (EPSG:2154).
    pulled_statuses : itérable de libellés source considérés comme « tirés ».
    buffer_m : rayon de recherche autour du poteau, en mètres.
    selected_pole_states : itérable de libellés d'état poteau à analyser.
        ``None`` => tous les poteaux sont analysés (pas de filtre d'état).
    selected_territoires : itérable de libellés de territoire / plaque à
        analyser. ``None`` ou vide => aucun filtre territoire.

    Retour
    ------
    rows : list[dict]
        Une ligne par poteau sortant (clés = colonnes résultat).
    counters : dict
        Compteurs d'analyse.
    cable_detail : list[dict]
        Une ligne par couple (poteau sortant, câble rattaché).
    """
    pulled_norm = normalized_status_set(pulled_statuses)
    pole_states_norm = None
    if selected_pole_states is not None:
        pole_states_norm = {normalize_status(s) for s in selected_pole_states}
    territoires_norm = None
    if selected_territoires:
        territoires_norm = {normalize_status(t) for t in selected_territoires}

    # Index spatial des câbles (pré-filtre par bounding box).
    cell = max(float(buffer_m), 1.0)
    grid = SpatialGrid(cell)
    for idx, cable in enumerate(cables):
        grid.insert(idx, bbox_of_lines(cable.lines))

    counters = {
        "poles_total": len(poles),
        "poles_selected": 0,
        "cables_total": len(cables),
        "poles_without_pulled": 0,
        "cable_status_distinct": len(
            {normalize_status(c.status) for c in cables}
        ),
    }

    rows = []
    cable_detail = []

    for pole in poles:
        if pole_states_norm is not None:
            if normalize_status(pole.state) not in pole_states_norm:
                continue
        if territoires_norm is not None:
            terr = pole.attrs.get("territoire")
            if normalize_status(terr) not in territoires_norm:
                continue
        counters["poles_selected"] += 1

        linked = []  # list of (cable, distance)
        if pole.xy is not None:
            px, py = pole.xy
            qbbox = (px - buffer_m, py - buffer_m, px + buffer_m, py + buffer_m)
            for idx in grid.query(qbbox):
                cable = cables[idx]
                dist = point_multiline_distance(pole.xy, cable.lines)
                if dist <= buffer_m:
                    linked.append((cable, dist))

        statuses_source = [c.status for c, _ in linked]
        statuses_norm = {normalize_status(s) for s in statuses_source}
        has_pulled = bool(statuses_norm & pulled_norm)
        if has_pulled:
            continue

        counters["poles_without_pulled"] += 1
        motif = MOTIF_NO_CABLE if not linked else MOTIF_NO_PULLED

        # Tous les câbles rattachés sont ici non tirés (sinon has_pulled).
        refs = [c.ref for c, _ in linked]
        a = pole.attrs
        rows.append({
            "id_poteau": pole.id,
            "commune": a.get("commune", ""),
            "departement": a.get("departement", ""),
            "territoire": a.get("territoire", ""),
            "etat_poteau": pole.state,
            "nb_cables": len(linked),
            "etats_cables": _join(statuses_source),
            "cables_associes": _join(refs),
            "cables_non_tires": _join(statuses_source),
            "motif": motif,
            "rayon_buffer_m": buffer_m,
            "nb_cables_intersectes": len(linked),
            "mode_rattachement": MODE_RATTACHEMENT,
            # Clés techniques (préfixe _) non affichées / non exportées en XLSX :
            # servent au zoom carte et à l'export shapefile.
            "_fid": pole.fid,
            "_xy": pole.xy,
        })

        for cable, dist in linked:
            ca = cable.attrs
            cable_detail.append({
                "id_poteau": pole.id,
                "ref_cable": cable.ref,
                "statut_cable": cable.status,
                "tire": False,
                "distance_m": round(dist, 2),
                "commune": ca.get("commune", ""),
                "departement": ca.get("departement", ""),
                "territoire": ca.get("territoire", ""),
            })

    return rows, counters, cable_detail
