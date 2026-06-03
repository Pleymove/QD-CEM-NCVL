from cem_ncvl_qgis_plugin.core.layer_mapping import (
    guess_field, guess_layer, guess_mapping,
)


def test_guess_layer_prefers_known_names():
    names = ["fond_osm", "0_cable_suivi.geom", "11_TRAVAUX_SUPPORTS.geom"]
    assert guess_layer(names, "poteaux") == "11_TRAVAUX_SUPPORTS.geom"
    assert guess_layer(names, "cables") == "0_cable_suivi.geom"


def test_guess_field_exact_before_substring():
    fields = ["id", "num_appui", "num_appui_orange", "commune"]
    # 'num_appui' (priorité) plutôt que l'id technique
    assert guess_field(fields, "id_poteau") == "num_appui"
    assert guess_field(fields, "commune") == "commune"


def test_guess_field_status():
    assert guess_field(["statut", "ref_cable"], "statut_cable") == "statut"
    assert guess_field(["ref_cable", "statut"], "ref_cable") == "ref_cable"


def test_guess_mapping_full():
    pole_fields = ["num_appui", "statut", "commune", "dept", "region"]
    cable_fields = ["ref_cable", "statut", "commune", "departement"]
    mapping = guess_mapping(pole_fields, cable_fields)
    assert mapping["id_poteau"] == "num_appui"
    assert mapping["etat_poteau"] == "statut"
    assert mapping["statut_cable"] == "statut"
    assert mapping["ref_cable"] == "ref_cable"
    assert mapping["departement"] == "dept"


def test_guess_returns_none_when_nothing_matches():
    assert guess_field(["xyz", "abc"], "commune") is None
    assert guess_layer([], "poteaux") is None
