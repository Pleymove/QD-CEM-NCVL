from cem_ncvl_qgis_plugin.core.synthese import (
    build_syntheses, build_tcd_table, count_by, EMPTY_LABEL,
)


def _rows():
    return [
        {"territoire": "T1", "departement": "33", "commune": "Bordeaux",
         "etat_poteau": "plante", "motif": "Aucun câble associé"},
        {"territoire": "T1", "departement": "33", "commune": "Bordeaux",
         "etat_poteau": "plante", "motif": "Aucun câble au statut tiré"},
        {"territoire": "T2", "departement": "47", "commune": "",
         "etat_poteau": "plante", "motif": "Aucun câble associé"},
    ]


def test_count_by_handles_empty_value():
    pairs = count_by(_rows(), "commune")
    as_dict = dict(pairs)
    assert as_dict["Bordeaux"] == 2
    assert as_dict[EMPTY_LABEL] == 1


def test_count_by_sorted_desc():
    pairs = count_by(_rows(), "territoire")
    assert pairs[0] == ("T1", 2)


def test_build_syntheses_keys():
    syn = build_syntheses(_rows(), [])
    assert "Par territoire / plaque" in syn
    assert "Par commune" in syn
    assert "Par motif de sortie" in syn


def test_build_tcd_table_aggregates():
    table = build_tcd_table(_rows())
    total = sum(entry["nb_poteaux"] for entry in table)
    assert total == 3
    # T1/33/Bordeaux/plante apparaît avec 2 motifs distincts -> 2 lignes
    bordeaux = [e for e in table if e["commune"] == "Bordeaux"]
    assert sum(e["nb_poteaux"] for e in bordeaux) == 2
