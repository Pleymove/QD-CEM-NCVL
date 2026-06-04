"""Tests de la règle métier GC v1.1.1 : reste à faire en optique > seuil."""

from cem_ncvl_qgis_plugin.core.models import GcArtere, Cable
from cem_ncvl_qgis_plugin.core.gc_analysis import (
    analyze_gc, DEFAULT_GC_DONE_STATES, DEFAULT_RESTE_SEUIL_ML, MOTIF_RESTE,
)
from cem_ncvl_qgis_plugin.core.cable_filters import DEFAULT_PULLED_STATUSES


def _gc(state="TRX fini", x0=0.0, x1=100.0, territoire="P1", fid=1):
    return GcArtere(id="A", label="GC-A", state=state,
                    lines=[[(x0, 0.0), (x1, 0.0)]],
                    attrs={"territoire": territoire}, fid=fid)


def _cable(status, x0, x1, y=0.5, ref="c"):
    return Cable(ref=ref, status=status, lines=[[(x0, y), (x1, y)]])


def _run(gcs, cables, seuil=DEFAULT_RESTE_SEUIL_ML, territoires=None):
    return analyze_gc(
        gcs, cables, DEFAULT_PULLED_STATUSES, buffer_m=1.0,
        selected_done_states=DEFAULT_GC_DONE_STATES,
        selected_territoires=territoires, seuil_reste_ml=seuil)


def test_gc_without_any_cable_outputs():
    rows, counters, _ = _run([_gc()], [])
    assert len(rows) == 1
    r = rows[0]
    assert r["motif"] == MOTIF_RESTE
    assert r["longueur_couverte"] == 0.0
    assert abs(r["ml_restant_optique"] - 100.0) < 1e-6
    assert counters["gc_reste_optique"] == 1


def test_gc_fully_covered_by_pulled_does_not_output():
    rows, _, _ = _run([_gc()], [_cable("Tiré", 0.0, 100.0)])
    assert rows == []


def test_gc_with_non_pulled_cable_outputs_full_remainder():
    rows, _, _ = _run([_gc()], [_cable("en_cours", 0.0, 100.0)])
    assert len(rows) == 1
    # un câble non tiré ne couvre pas optiquement
    assert rows[0]["longueur_couverte"] == 0.0
    assert rows[0]["nb_cables"] == 1


def test_gc_partially_covered_remainder_above_threshold_outputs():
    rows, _, _ = _run([_gc()], [_cable("Tiré", 0.0, 40.0)])
    assert len(rows) == 1
    r = rows[0]
    assert 38.0 <= r["longueur_couverte"] <= 43.0
    assert 57.0 <= r["ml_restant_optique"] <= 62.0


def test_gc_partially_covered_remainder_at_or_below_threshold_no_output():
    # couvert 0..80 -> reste ~20 <= 50 -> ne sort pas
    rows, _, _ = _run([_gc()], [_cable("Tiré", 0.0, 80.0)])
    assert rows == []


def test_seuil_configurable():
    cables = [_cable("Tiré", 0.0, 40.0)]  # reste ~60
    assert _run([_gc()], cables, seuil=100.0)[0] == []  # 60 <= 100 -> non
    assert len(_run([_gc()], cables, seuil=20.0)[0]) == 1  # 60 > 20 -> oui


def test_no_double_counting_with_overlapping_cables():
    cables = [
        _cable("Tiré", 0.0, 40.0, ref="c1"),
        _cable("Tirage fini", 0.0, 40.0, ref="c2"),  # même portion
    ]
    rows, _, _ = _run([_gc()], cables)
    assert len(rows) == 1
    # la portion couverte reste ~40, pas ~80
    assert rows[0]["longueur_couverte"] <= 43.0


def test_done_state_filter_excludes_non_done_gc():
    rows, counters, _ = _run([_gc(state="Go TRX")], [])
    assert rows == []
    assert counters["gc_selected"] == 0


def test_territoire_filter():
    gcs = [_gc(territoire="P1", fid=1), _gc(territoire="P2", fid=2)]
    gcs[1].id = "B"
    rows, counters, _ = _run(gcs, [], territoires=["P1"])
    assert {r["id_gc"] for r in rows} == {"A"}
    assert counters["gc_selected"] == 1


def test_rows_carry_fid_and_lines():
    rows, _, _ = _run([_gc(fid=7)], [])
    assert rows[0]["_fid"] == 7
    assert rows[0]["_lines"] == [[(0.0, 0.0), (100.0, 0.0)]]
    assert rows[0]["seuil_reste_optique"] == DEFAULT_RESTE_SEUIL_ML
