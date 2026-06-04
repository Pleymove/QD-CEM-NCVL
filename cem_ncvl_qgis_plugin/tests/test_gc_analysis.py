"""Tests de la règle métier GC souterrain (analyse spatiale ligne↔ligne)."""

from cem_ncvl_qgis_plugin.core.models import GcArtere, Cable
from cem_ncvl_qgis_plugin.core.gc_analysis import (
    analyze_gc, DEFAULT_GC_DONE_STATES, MOTIF_NO_CABLE, MOTIF_NO_PULLED,
)
from cem_ncvl_qgis_plugin.core.cable_filters import DEFAULT_PULLED_STATUSES


def _scenario():
    gcs = [
        GcArtere(id="A", label="GC-A", state="TRX fini",
                 lines=[[(0.0, 0.0), (100.0, 0.0)]],
                 attrs={"territoire": "P1"}),
        GcArtere(id="B", label="GC-B", state="facturation",
                 lines=[[(0.0, 1000.0), (100.0, 1000.0)]],
                 attrs={"territoire": "P2"}),
        GcArtere(id="C", label="GC-C", state="TRX fini",
                 lines=[[(0.0, 2000.0), (100.0, 2000.0)]],
                 attrs={"territoire": "P1"}),
        GcArtere(id="D", label="GC-D", state="Go TRX",
                 lines=[[(0.0, 0.0), (100.0, 0.0)]],
                 attrs={"territoire": "P1"}),
    ]
    cables = [
        # croise A (non tiré) -> A sort
        Cable(ref="c1", status="en_cours",
              lines=[[(50.0, -5.0), (50.0, 5.0)]]),
        # croise C (tiré) -> C ne sort pas
        Cable(ref="c2", status="Tiré",
              lines=[[(50.0, 1995.0), (50.0, 2005.0)]]),
    ]
    return gcs, cables


def test_gc_default_case():
    gcs, cables = _scenario()
    rows, counters, detail = analyze_gc(
        gcs, cables, DEFAULT_PULLED_STATUSES, buffer_m=1.0,
        selected_done_states=DEFAULT_GC_DONE_STATES)

    by_id = {r["id_gc"]: r for r in rows}
    assert set(by_id) == {"A", "B"}  # C a un câble tiré, D n'est pas 'travaux faits'
    assert by_id["A"]["motif"] == MOTIF_NO_PULLED
    assert by_id["A"]["nb_cables"] == 1
    assert by_id["B"]["motif"] == MOTIF_NO_CABLE
    assert by_id["B"]["nb_cables"] == 0

    assert counters["gc_total"] == 4
    assert counters["gc_selected"] == 3   # A, B, C (états travaux faits)
    assert counters["gc_without_pulled"] == 2
    assert {d["id_gc"] for d in detail} == {"A"}


def test_gc_territoire_filter():
    gcs, cables = _scenario()
    rows, counters, _ = analyze_gc(
        gcs, cables, DEFAULT_PULLED_STATUSES, buffer_m=1.0,
        selected_done_states=DEFAULT_GC_DONE_STATES,
        selected_territoires=["P1"])
    # P1 => A et C retenus ; A sort, C a un câble tiré
    assert {r["id_gc"] for r in rows} == {"A"}
    assert counters["gc_selected"] == 2


def test_gc_rows_carry_fid_and_lines():
    gcs = [GcArtere(id="A", label="GC-A", state="TRX fini",
                    lines=[[(0.0, 0.0), (10.0, 0.0)]], fid=7)]
    rows, _, _ = analyze_gc(
        gcs, [], DEFAULT_PULLED_STATUSES, buffer_m=1.0,
        selected_done_states=DEFAULT_GC_DONE_STATES)
    assert rows[0]["_fid"] == 7
    assert rows[0]["_lines"] == [[(0.0, 0.0), (10.0, 0.0)]]
    assert rows[0]["motif"] == MOTIF_NO_CABLE


def test_gc_pulled_status_excludes():
    gcs = [GcArtere(id="A", label="GC-A", state="TRX fini",
                    lines=[[(0.0, 0.0), (100.0, 0.0)]])]
    cables = [Cable(ref="c", status=" tirage fini ",
                    lines=[[(50.0, -1.0), (50.0, 1.0)]])]
    rows, counters, _ = analyze_gc(
        gcs, cables, DEFAULT_PULLED_STATUSES, buffer_m=1.0,
        selected_done_states=DEFAULT_GC_DONE_STATES)
    assert rows == []  # câble « tirage fini » (casse/espaces) détecté
    assert counters["gc_without_pulled"] == 0
