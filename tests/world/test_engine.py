"""Tests for ogar.world.engine — WorldEngine tick, run, history, inject_ignition."""

import pytest

from ogar.world.engine import WorldEngine, GroundTruthSnapshot
from ogar.world.grid import TerrainGrid, TerrainType, FireState
from ogar.world.weather import WeatherState
from ogar.world.fire_spread.heuristic import FireSpreadHeuristic


class TestWorldEngineTick:
    def test_tick_returns_snapshot(self, engine):
        snap = engine.tick()
        assert isinstance(snap, GroundTruthSnapshot)

    def test_tick_increments_counter(self, engine):
        assert engine.current_tick == 0
        engine.tick()
        assert engine.current_tick == 1
        engine.tick()
        assert engine.current_tick == 2

    def test_tick_records_history(self, engine):
        assert len(engine.history) == 0
        engine.tick()
        assert len(engine.history) == 1
        engine.tick()
        assert len(engine.history) == 2

    def test_snapshot_has_correct_tick(self, engine):
        snap = engine.tick()
        assert snap.tick == 0
        snap2 = engine.tick()
        assert snap2.tick == 1

    def test_snapshot_has_weather_dict(self, engine):
        snap = engine.tick()
        assert "temperature_c" in snap.weather
        assert "humidity_pct" in snap.weather

    def test_snapshot_has_cell_summary(self, engine):
        snap = engine.tick()
        assert "UNBURNED" in snap.cell_summary
        assert "BURNING" in snap.cell_summary
        assert "BURNED" in snap.cell_summary

    def test_snapshot_fire_intensity_map_dimensions(self, engine):
        snap = engine.tick()
        assert len(snap.fire_intensity_map) == 5
        assert len(snap.fire_intensity_map[0]) == 5


class TestWorldEngineRun:
    def test_run_returns_list_of_snapshots(self, engine):
        snapshots = engine.run(ticks=10)
        assert len(snapshots) == 10
        assert all(isinstance(s, GroundTruthSnapshot) for s in snapshots)

    def test_run_advances_tick(self, engine):
        engine.run(ticks=5)
        assert engine.current_tick == 5

    def test_run_zero_ticks(self, engine):
        snapshots = engine.run(ticks=0)
        assert snapshots == []
        assert engine.current_tick == 0


class TestWorldEngineHistory:
    def test_get_snapshot_valid(self, engine):
        engine.run(ticks=5)
        snap = engine.get_snapshot(2)
        assert snap is not None
        assert snap.tick == 2

    def test_get_snapshot_invalid(self, engine):
        engine.run(ticks=3)
        assert engine.get_snapshot(5) is None
        assert engine.get_snapshot(-1) is None


class TestInjectIgnition:
    def test_ignite_burnable_cell(self, engine):
        engine.inject_ignition(row=2, col=2, intensity=0.8)
        cell = engine.grid.get_cell(2, 2)
        assert cell.fire_state == FireState.BURNING
        assert cell.fire_intensity == 0.8

    def test_ignite_rock_does_nothing(self, engine):
        engine.grid.get_cell(2, 2).terrain_type = TerrainType.ROCK
        engine.grid.get_cell(2, 2).vegetation = 0.0
        engine.inject_ignition(row=2, col=2, intensity=0.8)
        cell = engine.grid.get_cell(2, 2)
        assert cell.fire_state == FireState.UNBURNED

    def test_ignite_water_does_nothing(self, engine):
        engine.grid.get_cell(2, 2).terrain_type = TerrainType.WATER
        engine.grid.get_cell(2, 2).vegetation = 0.0
        engine.inject_ignition(row=2, col=2, intensity=0.8)
        cell = engine.grid.get_cell(2, 2)
        assert cell.fire_state == FireState.UNBURNED

    def test_ignite_already_burning(self, engine):
        engine.grid.get_cell(2, 2).ignite(tick=0, intensity=0.5)
        engine.inject_ignition(row=2, col=2, intensity=0.9)
        cell = engine.grid.get_cell(2, 2)
        assert cell.fire_state == FireState.BURNING
        assert cell.fire_intensity == 0.5


class TestFireSpreadIntegration:
    def test_fire_spreads_over_ticks(self):
        """With ignition and favorable conditions, fire should spread."""
        grid = TerrainGrid(rows=5, cols=5)
        for r in range(5):
            for c in range(5):
                grid.get_cell(r, c).vegetation = 0.8
                grid.get_cell(r, c).fuel_moisture = 0.05
        weather = WeatherState(
            temperature_c=40.0,
            humidity_pct=5.0,
            wind_speed_mps=10.0,
            wind_direction_deg=225.0,
        )
        fire_spread = FireSpreadHeuristic(base_probability=0.5, burn_duration_ticks=10)
        engine = WorldEngine(grid=grid, weather=weather, fire_spread=fire_spread)
        engine.inject_ignition(row=4, col=0, intensity=0.9)

        engine.run(ticks=15)
        burning_or_burned = sum(
            1 for r in range(5) for c in range(5)
            if grid.get_cell(r, c).fire_state in (FireState.BURNING, FireState.BURNED)
        )
        assert burning_or_burned > 1
