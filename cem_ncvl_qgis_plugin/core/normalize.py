"""Fonctions de normalisation des valeurs.

Les comparaisons métier (clés, statuts) se font sur des valeurs normalisées,
mais l'export conserve toujours les libellés source d'origine.
"""


def normalize_key(value):
    """Normalise une clé de jointure / identifiant : trim + majuscules."""
    if value is None:
        return ""
    return str(value).strip().upper()


def normalize_status(value):
    """Normalise un statut pour comparaison : trim + minuscules."""
    if value is None:
        return ""
    return str(value).strip().lower()


def normalized_status_set(statuses):
    """Renvoie l'ensemble des statuts normalisés non vides."""
    result = set()
    for status in statuses:
        norm = normalize_status(status)
        if norm:
            result.add(norm)
    return result
