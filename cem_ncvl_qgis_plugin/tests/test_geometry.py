import math

from cem_ncvl_qgis_plugin.core.geometry import (
    bbox_of_lines, point_multiline_distance, point_polyline_distance,
    SpatialGrid,
)


def test_point_polyline_distance_perpendicular():
    line = [(0.0, 0.0), (10.0, 0.0)]
    assert point_polyline_distance((5.0, 3.0), line) == 3.0


def test_point_polyline_distance_beyond_endpoint():
    line = [(0.0, 0.0), (10.0, 0.0)]
    # au-delà de l'extrémité : distance à l'extrémité B
    assert point_polyline_distance((13.0, 4.0), line) == 5.0


def test_point_polyline_single_point():
    assert point_polyline_distance((3.0, 4.0), [(0.0, 0.0)]) == 5.0


def test_point_multiline_takes_minimum():
    lines = [[(0.0, 0.0), (10.0, 0.0)], [(0.0, 100.0), (10.0, 100.0)]]
    assert point_multiline_distance((5.0, 2.0), lines) == 2.0


def test_bbox_of_lines():
    lines = [[(1.0, 2.0), (3.0, 8.0)], [(-1.0, 0.0), (5.0, 4.0)]]
    assert bbox_of_lines(lines) == (-1.0, 0.0, 5.0, 8.0)
    assert bbox_of_lines([]) is None


def test_spatial_grid_query_finds_overlapping():
    grid = SpatialGrid(5.0)
    grid.insert(0, (0.0, 0.0, 1.0, 1.0))
    grid.insert(1, (100.0, 100.0, 101.0, 101.0))
    near = grid.query((-5.0, -5.0, 5.0, 5.0))
    assert 0 in near
    assert 1 not in near
