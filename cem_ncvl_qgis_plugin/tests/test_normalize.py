from cem_ncvl_qgis_plugin.core.normalize import (
    normalize_key, normalize_status, normalized_status_set,
)


def test_normalize_key_trims_and_uppercases():
    assert normalize_key("  ab12 ") == "AB12"
    assert normalize_key(None) == ""
    assert normalize_key(42) == "42"


def test_normalize_status_trims_and_lowercases():
    assert normalize_status("  Tiré ") == "tiré"
    assert normalize_status("Tirage Fini") == "tirage fini"
    assert normalize_status(None) == ""


def test_normalized_status_set_drops_empty():
    result = normalized_status_set(["Tiré", "  ", None, "tiré"])
    assert result == {"tiré"}
