"""
Shared fixtures for all ogar tests.

Seeding random ensures deterministic results across all test modules.
"""

import random
import pytest

from ogar.world.grid import TerrainGrid, TerrainType, Cell, FireState
from ogar.world.weather import WeatherState
from ogar.world.fire_spread.heuristic import FireSpreadHeuristic
from ogar.world.engine import WorldEngine
from ogar.transport.schemas import SensorEvent


@pytest.fixture(autouse=True)
def seed_random():
    """Seed RNG before every test for determinism."""
    random.seed(42)
    yield


@pytest.fixture
def small_grid() -> TerrainGrid:
    """A 5x5 grassland grid with default settings."""
    return TerrainGrid(rows=5, cols=5)


@pytest.fixture
def weather() -> WeatherState:
    """Hot, dry, windy weather — ideal for fire spread tests."""
    return WeatherState(
        temperature_c=38.0,
        humidity_pct=12.0,
        wind_speed_mps=8.0,
        wind_direction_deg=225.0,
        pressure_hpa=1008.0,
    )


@pytest.fixture
def fire_spread() -> FireSpreadHeuristic:
    return FireSpreadHeuristic(base_probability=0.15, burn_duration_ticks=5)


@pytest.fixture
def engine(small_grid, weather, fire_spread) -> WorldEngine:
    """A WorldEngine with a 5x5 grid, hot/dry weather, and heuristic fire spread."""
    return WorldEngine(grid=small_grid, weather=weather, fire_spread=fire_spread)


@pytest.fixture
def sample_event() -> SensorEvent:
    """A pre-built SensorEvent for transport/agent tests."""
    return SensorEvent.create(
        source_id="temp-A1",
        source_type="temperature",
        cluster_id="cluster-north",
        payload={"celsius": 42.1},
        confidence=0.95,
    )
