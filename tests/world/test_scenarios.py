"""Tests for ogar.world.scenarios — factory functions."""

from ogar.world.scenarios.wildfire_basic import create_basic_wildfire
from ogar.world.engine import WorldEngine
from ogar.world.grid import TerrainType, FireState


class TestBasicWildfireScenario:
    def test_returns_engine(self):
        engine = create_basic_wildfire()
        assert isinstance(engine, WorldEngine)

    def test_grid_dimensions(self):
        engine = create_basic_wildfire()
        assert engine.grid.rows == 10
        assert engine.grid.cols == 10

    def test_initial_ignition_at_7_2(self):
        engine = create_basic_wildfire()
        cell = engine.grid.get_cell(7, 2)
        assert cell.fire_state == FireState.BURNING
        assert cell.fire_intensity == 0.8

    def test_water_in_northwest(self):
        engine = create_basic_wildfire()
        assert engine.grid.get_cell(0, 0).terrain_type == TerrainType.WATER
        assert engine.grid.get_cell(1, 0).terrain_type == TerrainType.WATER

    def test_forest_in_north(self):
        engine = create_basic_wildfire()
        assert engine.grid.get_cell(2, 5).terrain_type == TerrainType.FOREST

    def test_rock_ridge_at_row_4(self):
        engine = create_basic_wildfire()
        assert engine.grid.get_cell(4, 0).terrain_type == TerrainType.ROCK
        assert engine.grid.get_cell(4, 6).terrain_type == TerrainType.SCRUB
        assert engine.grid.get_cell(4, 7).terrain_type == TerrainType.SCRUB

    def test_grassland_in_south(self):
        engine = create_basic_wildfire()
        assert engine.grid.get_cell(6, 3).terrain_type == TerrainType.GRASSLAND

    def test_urban_in_southeast(self):
        engine = create_basic_wildfire()
        assert engine.grid.get_cell(7, 8).terrain_type == TerrainType.URBAN
        assert engine.grid.get_cell(8, 9).terrain_type == TerrainType.URBAN

    def test_weather_conditions(self):
        engine = create_basic_wildfire()
        assert engine.weather.temperature_c == 38.0
        assert engine.weather.humidity_pct == 12.0
        assert engine.weather.wind_speed_mps == 8.0
        assert engine.weather.wind_direction_deg == 225.0

    def test_engine_can_tick(self):
        engine = create_basic_wildfire()
        snap = engine.tick()
        assert snap.tick == 0
