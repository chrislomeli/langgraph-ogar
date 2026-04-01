"""Tests for ogar.world.fire_spread — interface + heuristic."""

import random

import pytest

from ogar.world.fire_spread.interface import FireEvent, FireEventType, FireSpreadModule
from ogar.world.fire_spread.heuristic import FireSpreadHeuristic
from ogar.world.grid import TerrainGrid, TerrainType, FireState
from ogar.world.weather import WeatherState


# ── Interface / dataclass tests ──────────────────────────────────────────────

class TestFireEvent:
    def test_fire_event_fields(self):
        e = FireEvent(row=3, col=4, event_type=FireEventType.IGNITED, intensity=0.7)
        assert e.row == 3
        assert e.col == 4
        assert e.event_type == FireEventType.IGNITED
        assert e.intensity == 0.7

    def test_fire_event_type_values(self):
        assert FireEventType.IGNITED == "IGNITED"
        assert FireEventType.EXTINGUISHED == "EXTINGUISHED"
        assert FireEventType.INTENSIFIED == "INTENSIFIED"

    def test_fire_spread_module_is_abstract(self):
        with pytest.raises(TypeError):
            FireSpreadModule()


# ── Heuristic: burn duration / extinguish ────────────────────────────────────

class TestBurnDuration:
    def test_cell_extinguishes_after_burn_duration(self):
        grid = TerrainGrid(rows=3, cols=3)
        grid.get_cell(1, 1).ignite(tick=0, intensity=0.5)
        weather = WeatherState(humidity_pct=90.0, wind_speed_mps=0.0)
        heuristic = FireSpreadHeuristic(base_probability=0.0, burn_duration_ticks=3)

        events = heuristic.tick_fire(grid=grid, weather=weather, tick=3)
        ext_events = [e for e in events if e.event_type == FireEventType.EXTINGUISHED]
        assert len(ext_events) == 1
        assert ext_events[0].row == 1
        assert ext_events[0].col == 1

    def test_cell_does_not_extinguish_early(self):
        grid = TerrainGrid(rows=3, cols=3)
        grid.get_cell(1, 1).ignite(tick=0, intensity=0.5)
        weather = WeatherState(humidity_pct=90.0, wind_speed_mps=0.0)
        heuristic = FireSpreadHeuristic(base_probability=0.0, burn_duration_ticks=5)

        events = heuristic.tick_fire(grid=grid, weather=weather, tick=3)
        ext_events = [e for e in events if e.event_type == FireEventType.EXTINGUISHED]
        assert len(ext_events) == 0


# ── Heuristic: spread probability factors ────────────────────────────────────

class TestHumidityFactor:
    def test_low_humidity_high_factor(self):
        factor = FireSpreadHeuristic._compute_humidity_factor(5.0)
        assert factor > 1.0

    def test_high_humidity_low_factor(self):
        factor = FireSpreadHeuristic._compute_humidity_factor(80.0)
        assert factor < 1.0

    def test_humidity_factor_clamped_range(self):
        f_low = FireSpreadHeuristic._compute_humidity_factor(0.0)
        f_high = FireSpreadHeuristic._compute_humidity_factor(100.0)
        assert f_low == 1.5
        assert f_high == pytest.approx(0.2)


class TestSpreadProbability:
    def test_high_probability_downwind_dry(self):
        """Downwind, dry fuel, high vegetation → high spread chance."""
        grid = TerrainGrid(rows=3, cols=3)
        grid.get_cell(1, 1).ignite(tick=0, intensity=0.8)
        grid.get_cell(0, 2).fuel_moisture = 0.0
        grid.get_cell(0, 2).vegetation = 1.0

        weather = WeatherState(
            wind_direction_deg=225.0,
            wind_speed_mps=12.0,
            humidity_pct=5.0,
        )
        heuristic = FireSpreadHeuristic(base_probability=0.5)

        random.seed(42)
        events = heuristic.tick_fire(grid=grid, weather=weather, tick=1)
        ignitions = [e for e in events if e.event_type == FireEventType.IGNITED]
        assert len(ignitions) > 0

    def test_no_spread_to_rock(self):
        grid = TerrainGrid(rows=3, cols=3)
        grid.get_cell(1, 1).ignite(tick=0, intensity=0.8)
        for r, c in grid.neighbors(1, 1):
            grid.get_cell(r, c).terrain_type = TerrainType.ROCK
            grid.get_cell(r, c).vegetation = 0.0

        weather = WeatherState(humidity_pct=5.0, wind_speed_mps=10.0)
        heuristic = FireSpreadHeuristic(base_probability=1.0)

        events = heuristic.tick_fire(grid=grid, weather=weather, tick=1)
        ignitions = [e for e in events if e.event_type == FireEventType.IGNITED]
        assert len(ignitions) == 0

    def test_no_spread_to_water(self):
        grid = TerrainGrid(rows=3, cols=3)
        grid.get_cell(1, 1).ignite(tick=0, intensity=0.8)
        for r, c in grid.neighbors(1, 1):
            grid.get_cell(r, c).terrain_type = TerrainType.WATER
            grid.get_cell(r, c).vegetation = 0.0

        weather = WeatherState()
        heuristic = FireSpreadHeuristic(base_probability=1.0)

        events = heuristic.tick_fire(grid=grid, weather=weather, tick=1)
        ignitions = [e for e in events if e.event_type == FireEventType.IGNITED]
        assert len(ignitions) == 0

    def test_no_double_ignition(self):
        """A cell should not be ignited twice in the same tick."""
        grid = TerrainGrid(rows=3, cols=3)
        grid.get_cell(0, 1).ignite(tick=0, intensity=0.9)
        grid.get_cell(1, 0).ignite(tick=0, intensity=0.9)

        weather = WeatherState(humidity_pct=5.0, wind_speed_mps=0.0)
        heuristic = FireSpreadHeuristic(base_probability=1.0, burn_duration_ticks=10)

        events = heuristic.tick_fire(grid=grid, weather=weather, tick=1)
        ignited_coords = [(e.row, e.col) for e in events if e.event_type == FireEventType.IGNITED]
        assert len(ignited_coords) == len(set(ignited_coords))

    def test_no_events_when_no_fire(self):
        grid = TerrainGrid(rows=3, cols=3)
        weather = WeatherState()
        heuristic = FireSpreadHeuristic()
        events = heuristic.tick_fire(grid=grid, weather=weather, tick=0)
        assert events == []

    def test_probability_capped_at_095(self):
        heuristic = FireSpreadHeuristic(base_probability=10.0)
        grid = TerrainGrid(rows=3, cols=3)
        grid.get_cell(1, 1).ignite(tick=0, intensity=1.0)
        grid.get_cell(0, 0).vegetation = 1.0
        grid.get_cell(0, 0).fuel_moisture = 0.0

        prob = heuristic._spread_probability(
            1, 1, 0, 0,
            grid.get_cell(1, 1), grid.get_cell(0, 0),
            -0.7, 0.7, 15.0,
            1.5,
        )
        assert prob <= 0.95
