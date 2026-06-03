"""Tests de la règle métier principale (analyse spatiale des poteaux)."""

from cem_ncvl_qgis_plugin.core.models import Pole, Cable
from cem_ncvl_qgis_plugin.core.poteaux_analysis import (
    analyze, MOTIF_NO_CABLE, MOTIF_NO_PULLED,
)
from cem_ncvl_qgis_plugin.core.cable_filters import DEFAULT_PULLED_STATUSES


def _scenario():
    poles = [
        Pole(id="A", state="plante", xy=(0.0, 0.0)),       # câble non tiré proche
        Pole(id="B", state="plante", xy=(50.0, 50.0)),     # aucun câble proche
        Pole(id="C", state="plante", xy=(100.0, 0.0)),     # câble tiré proche
        Pole(id="D", state="programme", xy=(0.0, 0.0)),    # exclu par l'état
    ]
    cables = [
        Cable(ref="c1", status="en_cours", lines=[[(0.0, 3.0), (10.0, 3.0)]]),
        Cable(ref="c2", status="Tiré", lines=[[(100.0, 2.0), (110.0, 2.0)]]),
    ]
    return poles, cables


def test_default_case_outputs_poles_without_pulled_cable():
    poles, cables = _scenario()
    rows, counters, detail = analyze(
        poles, cables, DEFAULT_PULLED_STATUSES,
        buffer_m=5.0, selected_pole_states=["plante"])

    out_ids = {r["id_poteau"] for r in rows}
    assert out_ids == {"A", "B"}  # C a un câble tiré, D n'est pas 'plante'

    by_id = {r["id_poteau"]: r for r in rows}
    assert by_id["A"]["motif"] == MOTIF_NO_PULLED
    assert by_id["A"]["nb_cables"] == 1
    assert by_id["B"]["motif"] == MOTIF_NO_CABLE
    assert by_id["B"]["nb_cables"] == 0

    assert counters["poles_total"] == 4
    assert counters["poles_selected"] == 3
    assert counters["cables_total"] == 2
    assert counters["poles_without_pulled"] == 2

    # le détail câble ne concerne que les poteaux sortis
    assert {d["id_poteau"] for d in detail} == {"A"}
    assert detail[0]["ref_cable"] == "c1"
    assert detail[0]["tire"] is False


def test_buffer_changes_attachment():
    poles, cables = _scenario()
    # buffer réduit à 2 m : le câble c1 (distance 3 m) n'est plus rattaché à A
    rows, counters, _ = analyze(
        poles, cables, DEFAULT_PULLED_STATUSES,
        buffer_m=2.0, selected_pole_states=["plante"])
    by_id = {r["id_poteau"]: r for r in rows}
    assert by_id["A"]["nb_cables"] == 0
    assert by_id["A"]["motif"] == MOTIF_NO_CABLE


def test_pulled_status_normalized_excludes_pole():
    poles = [Pole(id="X", state="plante", xy=(0.0, 0.0))]
    cables = [Cable(ref="c", status="  tiré ", lines=[[(0.0, 1.0), (5.0, 1.0)]])]
    rows, counters, _ = analyze(
        poles, cables, ["Tiré"], buffer_m=5.0,
        selected_pole_states=["plante"])
    assert rows == []  # le câble « tiré » (casse/espaces) est bien détecté
    assert counters["poles_without_pulled"] == 0


def test_no_pole_state_filter_keeps_all_poles():
    poles, cables = _scenario()
    rows, counters, _ = analyze(
        poles, cables, DEFAULT_PULLED_STATUSES,
        buffer_m=5.0, selected_pole_states=None)
    # D (programme) à (0,0) est aussi analysé ; il a le câble non tiré c1
    assert counters["poles_selected"] == 4
    assert "D" in {r["id_poteau"] for r in rows}
