from cem_ncvl_qgis_plugin.core.cable_filters import (
    DEFAULT_PULLED_STATUSES, has_pulled_cable, split_pulled,
)


def test_default_pulled_statuses():
    assert DEFAULT_PULLED_STATUSES == ["Tiré", "Tirage fini"]


def test_has_pulled_cable_normalized_match():
    # casse / espaces différents mais sémantiquement « tiré »
    assert has_pulled_cable([" tiré "], ["Tiré", "Tirage fini"]) is True
    assert has_pulled_cable(["en_cours", "Blocage"], DEFAULT_PULLED_STATUSES) \
        is False
    assert has_pulled_cable([], DEFAULT_PULLED_STATUSES) is False


def test_split_pulled_keeps_source_labels():
    tires, non_tires = split_pulled(
        ["Tiré", "en_cours", "Tirage fini", "Blocage"],
        DEFAULT_PULLED_STATUSES)
    assert tires == ["Tiré", "Tirage fini"]
    assert non_tires == ["en_cours", "Blocage"]
