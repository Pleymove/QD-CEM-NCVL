"""Présélection intelligente des couches et des champs.

Logique pure (aucune dépendance QGIS) : à partir de noms de couches / champs,
on devine le meilleur candidat via des mots-clés. Les noms ne sont jamais
codés en dur côté analyse : ce module ne fournit que des *suggestions* que
l'utilisateur peut corriger dans l'interface.

Indices issus du brief CEM NCVL :
- couche poteaux : ``11_TRAVAUX_SUPPORTS`` (points) ;
- couche câbles  : ``0_cable_suivi`` (lignes) ;
- champs câble   : ``statut``, ``ref_cable``, ``commune``, ``departement`` ;
- champs support : ``id``, ``num_appui``, ``statut``, ``commune``, ``insee``.
"""

# Mots-clés (en minuscules) par rôle. L'ordre traduit la priorité.
LAYER_HINTS = {
    "poteaux": ["11_travaux_supports", "travaux_supports", "support",
                "poteau", "appui"],
    "cables": ["0_cable_suivi", "cable_suivi", "cable", "câble"],
}

FIELD_HINTS = {
    "id_poteau": ["num_appui", "id__pa", "num_appui_orange", "id"],
    "etat_poteau": ["statut", "etat"],
    "travaux": ["travaux", "trvx", "type_travaux"],
    "ref_cable": ["ref_cable", "ref", "reference"],
    "statut_cable": ["statut", "etat", "status"],
    "commune": ["commune", "ville"],
    "departement": ["departement", "département", "dept", "dep"],
    "territoire": ["code_imputation", "zone_exe", "code_proje", "territoire",
                   "plaque", "secteur", "region"],
}


def _best_match(candidates, keywords):
    """Renvoie le candidat dont le nom correspond le mieux aux mots-clés.

    Stratégie : pour chaque mot-clé (par priorité), on cherche d'abord une
    égalité exacte (insensible à la casse), puis une inclusion. Le premier
    mot-clé qui produit un résultat l'emporte.
    """
    if not candidates:
        return None
    lowered = [(c, c.lower()) for c in candidates]
    for keyword in keywords:
        for original, low in lowered:
            if low == keyword:
                return original
    for keyword in keywords:
        for original, low in lowered:
            if keyword in low:
                return original
    return None


def guess_layer(layer_names, role):
    """Devine la couche pour un rôle (``"poteaux"`` ou ``"cables"``)."""
    return _best_match(layer_names, LAYER_HINTS.get(role, []))


def guess_field(field_names, role):
    """Devine le champ pour un rôle (clé de ``FIELD_HINTS``)."""
    return _best_match(field_names, FIELD_HINTS.get(role, []))


def guess_mapping(pole_fields, cable_fields):
    """Devine l'ensemble du mapping de champs.

    Retour : dict avec les clés ``id_poteau``, ``etat_poteau`` (côté poteaux),
    ``ref_cable``, ``statut_cable`` (côté câbles) et les champs optionnels
    ``commune`` / ``departement`` / ``territoire`` côté poteaux.
    """
    return {
        "id_poteau": guess_field(pole_fields, "id_poteau"),
        "etat_poteau": guess_field(pole_fields, "etat_poteau"),
        "commune": guess_field(pole_fields, "commune"),
        "departement": guess_field(pole_fields, "departement"),
        "territoire": guess_field(pole_fields, "territoire"),
        "ref_cable": guess_field(cable_fields, "ref_cable"),
        "statut_cable": guess_field(cable_fields, "statut_cable"),
    }
