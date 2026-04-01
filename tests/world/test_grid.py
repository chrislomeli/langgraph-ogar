"""Tests for ogar.world.grid — Cell, TerrainGrid, enums."""

import pytest

from ogar.world.grid import Cell, TerrainGrid, TerrainType, FireState


# ── Enum tests ───────────────────────────────────────────────────────────────

class TestEnums:
    def test_terrain_type_values(self):
        assert TerrainType.FOREST == "FOREST"
        assert TerrainType.WATER == "WATER"
        assert len(TerrainType) == 6

    def test_fire_state_values(self):
        assert FireState.UNBURNED == "UNBURNED"
        assert FireState.BURNING == "BURNING"
        assert FireState.BURNED == "BURNED"
        assert len(FireState) == 3


# ── Cell tests ───────────────────────────────────────────────────────────────

class TestCell:
    def test_defaults(self):
        cell = Cell()
        assert cell.terrain_type == TerrainType.GRASSLAND
        assert cell.vegetation == 0.5
        assert cell.fuel_moisture == 0.3
        assert cell.slope == 0.0
        assert cell.fire_state == FireState.UNBURNED
        assert cell.fire_intensity == 0.0
        assert cell.fire_start_tick is None

    def test_custom_terrain(self):
        cell = Cell(terrain_type=TerrainType.FOREST, vegetation=0.9, fuel_moisture=0.1)
        assert cell.terrain_type == TerrainType.FOREST
        assert cell.vegetation == 0.9
        assert cell.fuel_moisture == 0.1

    def test_vegetation_clamped_high(self):
        cell = Cell(vegetation=2.0)
        assert cell.vegetation == 1.0

    def test_vegetation_clamped_low(self):
        cell = Cell(vegetation=-0.5)
        assert cell.vegetation == 0.0

    def test_fuel_moisture_clamped(self):
        cell = Cell(fuel_moisture=1.5)
        assert cell.fuel_moisture == 1.0
        cell2 = Cell(fuel_moisture=-0.2)
        assert cell2.fuel_moisture == 0.0

    def test_is_burnable_default(self):
        cell = Cell()
        assert cell.is_burnable is True

    def test_rock_not_burnable(self):
        cell = Cell(terrain_type=TerrainType.ROCK)
        assert cell.is_burnable is False

    def test_water_not_burnable(self):
        cell = Cell(terrain_type=TerrainType.WATER)
        assert cell.is_burnable is False

    def test_zero_vegetation_not_burnable(self):
        cell = Cell(vegetation=0.0)
        assert cell.is_burnable is False

    def test_burning_cell_not_burnable(self):
        cell = Cell()
        cell.ignite(tick=0, intensity=0.5)
        assert cell.is_burnable is False

    def test_burned_cell_not_burnable(self):
        cell = Cell()
        cell.ignite(tick=0)
        cell.extinguish()
        assert cell.is_burnable is False

    def test_ignite(self):
        cell = Cell()
        cell.ignite(tick=3, intensity=0.8)
        assert cell.fire_state == FireState.BURNING
        assert cell.fire_intensity == 0.8
        assert cell.fire_start_tick == 3

    def test_ignite_clamps_intensity(self):
        cell = Cell()
        cell.ignite(tick=0, intensity=1.5)
        assert cell.fire_intensity == 1.0
        cell2 = Cell()
        cell2.ignite(tick=0, intensity=-0.3)
        assert cell2.fire_intensity == 0.0

    def test_extinguish(self):
        cell = Cell()
        cell.ignite(tick=0, intensity=0.7)
        cell.extinguish()
        assert cell.fire_state == FireState.BURNED
        assert cell.fire_intensity == 0.0

    def test_to_dict(self):
        cell = Cell(terrain_type=TerrainType.FOREST, vegetation=0.85)
        d = cell.to_dict()
        assert d["terrain_type"] == "FOREST"
        assert d["vegetation"] == 0.85
        assert d["fire_state"] == "UNBURNED"


# ── TerrainGrid tests ────────────────────────────────────────────────────────

class TestTerrainGrid:
    def test_construction(self, small_grid):
        assert small_grid.rows == 5
        assert small_grid.cols == 5

    def test_invalid_dimensions(self):
        with pytest.raises(ValueError):
            TerrainGrid(rows=0, cols=5)
        with pytest.raises(ValueError):
            TerrainGrid(rows=5, cols=-1)

    def test_get_cell_valid(self, small_grid):
        cell = small_grid.get_cell(0, 0)
        assert isinstance(cell, Cell)

    def test_get_cell_out_of_bounds(self, small_grid):
        with pytest.raises(IndexError):
            small_grid.get_cell(5, 0)
        with pytest.raises(IndexError):
            small_grid.get_cell(0, 5)
        with pytest.raises(IndexError):
            small_grid.get_cell(-1, 0)

    def test_neighbors_center(self, small_grid):
        neighbors = small_grid.neighbors(2, 2)
        assert len(neighbors) == 8

    def test_neighbors_corner(self, small_grid):
        neighbors = small_grid.neighbors(0, 0)
        assert len(neighbors) == 3
        assert (0, 1) in neighbors
        assert (1, 0) in neighbors
        assert (1, 1) in neighbors

    def test_neighbors_edge(self, small_grid):
        neighbors = small_grid.neighbors(0, 2)
        assert len(neighbors) == 5

    def test_burning_cells_empty(self, small_grid):
        assert small_grid.burning_cells() == []

    def test_burning_cells_with_fire(self, small_grid):
        small_grid.get_cell(1, 1).ignite(tick=0)
        small_grid.get_cell(3, 3).ignite(tick=0)
        burning = small_grid.burning_cells()
        assert len(burning) == 2
        assert (1, 1) in burning
        assert (3, 3) in burning

    def test_fire_intensity_grid(self, small_grid):
        small_grid.get_cell(2, 2).ignite(tick=0, intensity=0.6)
        grid = small_grid.fire_intensity_grid()
        assert len(grid) == 5
        assert len(grid[0]) == 5
        assert grid[2][2] == 0.6
        assert grid[0][0] == 0.0

    def test_summary(self, small_grid):
        small_grid.get_cell(0, 0).ignite(tick=0)
        small_grid.get_cell(1, 1).ignite(tick=0)
        small_grid.get_cell(1, 1).extinguish()
        summary = small_grid.summary()
        assert summary["BURNING"] == 1
        assert summary["BURNED"] == 1
        assert summary["UNBURNED"] == 23

    def test_snapshot(self, small_grid):
        snap = small_grid.snapshot()
        assert snap["rows"] == 5
        assert snap["cols"] == 5
        assert len(snap["cells"]) == 5
        assert len(snap["cells"][0]) == 5
        assert snap["cells"][0][0]["terrain_type"] == "GRASSLAND"
