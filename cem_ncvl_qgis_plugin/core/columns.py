"""Définition centralisée des colonnes (clé interne -> libellé affiché)."""

# Feuille / tableau « Liste poteaux ».
POLE_COLUMNS = [
    ("id_poteau", "ID poteau"),
    ("commune", "Commune"),
    ("departement", "Département"),
    ("territoire", "Territoire / plaque"),
    ("etat_poteau", "État poteau"),
    ("travaux", "Travaux"),
    ("nb_cables", "Nombre câbles associés"),
    ("etats_cables", "États câbles trouvés"),
    ("cables_associes", "Câbles associés"),
    ("cables_non_tires", "Câbles non tirés"),
    ("motif", "Motif de sortie"),
    ("rayon_buffer_m", "Rayon buffer (m)"),
    ("nb_cables_intersectes", "Nb câbles intersectés"),
    ("mode_rattachement", "Mode rattachement"),
]

# Feuille « Câbles associés ».
CABLE_COLUMNS = [
    ("id_poteau", "ID poteau"),
    ("ref_cable", "Référence câble"),
    ("statut_cable", "Statut câble"),
    ("distance_m", "Distance (m)"),
    ("commune", "Commune"),
    ("departement", "Département"),
    ("territoire", "Territoire / plaque"),
]


# Feuille / tableau « GC souterrains ».
GC_COLUMNS = [
    ("id_gc", "ID GC"),
    ("nom_gc", "Nom / code GC"),
    ("commune", "Commune"),
    ("departement", "Département"),
    ("territoire", "Territoire / plaque"),
    ("suivi_pilotage", "Suivi travaux GC"),
    ("longueur", "Longueur (ml)"),
    ("nb_cables", "Nombre câbles associés"),
    ("etats_cables", "Statuts câbles trouvés"),
    ("cables_associes", "Câbles associés"),
    ("cables_non_tires", "Câbles non tirés"),
    ("motif", "Motif de sortie"),
    ("rayon_buffer_m", "Rayon buffer (m)"),
    ("nb_cables_intersectes", "Nb câbles intersectés"),
    ("mode_rattachement", "Mode rattachement"),
]

# Feuille « Câbles associés » côté GC (clé de liaison = id_gc).
CABLE_GC_COLUMNS = [
    ("id_gc", "ID GC"),
    ("ref_cable", "Référence câble"),
    ("statut_cable", "Statut câble"),
    ("distance_m", "Distance (m)"),
    ("commune", "Commune"),
    ("departement", "Département"),
    ("territoire", "Territoire / plaque"),
]


def column_keys(columns):
    return [key for key, _ in columns]


def column_labels(columns):
    return [label for _, label in columns]
