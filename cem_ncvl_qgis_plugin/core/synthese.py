"""Calcul des synthèses et de la table prête à pivoter (TCD)."""

from collections import Counter

EMPTY_LABEL = "(non renseigné)"


def count_by(rows, key):
    """Compte les lignes par valeur de ``key``, trié par effectif décroissant."""
    counter = Counter()
    for row in rows:
        value = row.get(key)
        label = EMPTY_LABEL if value in (None, "") else str(value)
        counter[label] += 1
    return sorted(counter.items(), key=lambda kv: (-kv[1], kv[0]))


def distribution_etats_cables(cable_detail):
    """Distribution des statuts de câble parmi les câbles rattachés sortis."""
    return count_by(cable_detail, "statut_cable")


def build_syntheses(rows, cable_detail):
    """Construit toutes les synthèses attendues côté onglet Récap TCD.

    Retour : dict ``titre -> [(libellé, effectif), ...]``.
    """
    return {
        "Par territoire / plaque": count_by(rows, "territoire"),
        "Par département": count_by(rows, "departement"),
        "Par commune": count_by(rows, "commune"),
        "Par motif de sortie": count_by(rows, "motif"),
        "Par état câble (câbles rattachés)":
            distribution_etats_cables(cable_detail),
    }


# Colonnes de la table « prête à pivoter » (une ligne par poteau sorti).
TCD_COLUMNS = [
    ("territoire", "Territoire / plaque"),
    ("departement", "Département"),
    ("commune", "Commune"),
    ("etat_poteau", "État poteau"),
    ("motif", "Motif de sortie"),
]


def build_tcd_table(rows):
    """Table à plat agrégée, prête à être pivotée dans Excel.

    Une ligne par combinaison (territoire, département, commune, état, motif)
    avec le nombre de poteaux. C'est le livrable robuste de remplacement d'un
    vrai TCD natif.
    """
    counter = Counter()
    for row in rows:
        key = tuple(
            (row.get(col) or EMPTY_LABEL) if row.get(col) not in (None, "")
            else EMPTY_LABEL
            for col, _ in TCD_COLUMNS
        )
        counter[key] += 1

    table = []
    for key, nb in sorted(counter.items(), key=lambda kv: (-kv[1], kv[0])):
        entry = {col: value for (col, _), value in zip(TCD_COLUMNS, key)}
        entry["nb_poteaux"] = nb
        table.append(entry)
    return table
