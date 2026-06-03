"""Gestion des statuts de câble considérés comme « tirés »."""

from .normalize import normalize_status, normalized_status_set

# Statuts proposés cochés par défaut dans l'interface (libellés source).
DEFAULT_PULLED_STATUSES = ["Tiré", "Tirage fini"]

# Statuts visibles dans la symbologie de la couche câble (aide à la saisie /
# présélection si la couche réelle n'est pas encore chargée). Source : brief
# CEM NCVL, champ ``statut`` de ``0_cable_suivi``.
KNOWN_CABLE_STATUSES = [
    "annule", "refus", "Etude", "exeok", "exeok-5pc", "Go tirage",
    "en_cours", "Tirage fini", "Tiré", "Blocage", "blocage_nego",
    "blocage_privé", "Blocage_etude", "desat", "desat_ok",
    "visite_terrain", "produit_terrain", "reprise_exe", "exeok_controle",
]


def has_pulled_cable(cable_statuses, pulled_statuses):
    """Vrai si au moins un statut de câble appartient aux statuts « tirés ».

    La comparaison se fait sur des valeurs normalisées (trim + minuscules).
    """
    pulled = normalized_status_set(pulled_statuses)
    found = normalized_status_set(cable_statuses)
    return bool(found & pulled)


def split_pulled(cable_statuses, pulled_statuses):
    """Sépare les statuts source en (tirés, non tirés) en conservant l'ordre."""
    pulled = normalized_status_set(pulled_statuses)
    tires = []
    non_tires = []
    for status in cable_statuses:
        if normalize_status(status) in pulled:
            tires.append(status)
        else:
            non_tires.append(status)
    return tires, non_tires
