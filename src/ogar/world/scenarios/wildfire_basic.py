"""
ogar.world.scenarios.wildfire_basic

A simple wildfire scenario on a 10×10 grid.

What this sets up
─────────────────
A small terrain grid with mixed terrain types:
  - Forest in the north half (high vegetation, moderate moisture)
  - Grassland in the south half (medium vegetation, low moisture)
  - A ridge of rock running east-west through the middle (acts as firebreak)
  - A small urban area in the south-east corner (buildings to protect)
  - A water feature in the north-west corner (lake, impassable)

Weather starts hot, dry, and windy from the south-west — ideal
conditions for fire to spread north-east through the grassland
and into the forest.

One fire ignition at cell (7, 2) — the south-west grassland.
This gives the fire room to spread and tests whether the agent
can detect it early from sensor readings.

Why this specific layout
─────────────────────────
  - The rock ridge creates a natural decision point: will the fire
    jump the ridge?  The agent has to monitor both sides.
  - The urban area in the path creates an actuator decision:
    should resources be dispatched to protect the buildings?
  - The lake blocks spread in one corner, creating asymmetric
    fire behaviour that tests the agent's spatial reasoning.
  - The forest-to-grassland transition means fire speed changes,
    which tests the agent's ability to detect changing patterns.
"""

from __future__ import annotations

from ogar.world.engine import WorldEngine
from ogar.world.grid import TerrainGrid, TerrainType
from ogar.world.weather import WeatherState
from ogar.world.fire_spread.heuristic import FireSpreadHeuristic


def create_basic_wildfire() -> WorldEngine:
    """
    Create and return a fully configured WorldEngine for the basic
    wildfire scenario.

    The engine is ready to tick — call engine.tick() or engine.run(N).

    Grid layout (10×10):

      Row 0 (north):  WATER  FOREST  FOREST  FOREST  FOREST  FOREST  FOREST  FOREST  FOREST  FOREST
      Row 1:          WATER  FOREST  FOREST  FOREST  FOREST  FOREST  FOREST  FOREST  FOREST  FOREST
      Row 2:          FOREST FOREST  FOREST  FOREST  FOREST  FOREST  FOREST  FOREST  FOREST  FOREST
      Row 3:          FOREST FOREST  FOREST  FOREST  FOREST  FOREST  FOREST  FOREST  FOREST  FOREST
      Row 4 (ridge):  ROCK   ROCK    ROCK    ROCK    ROCK    ROCK    SCRUB   SCRUB   ROCK    ROCK
      Row 5:          GRASS  GRASS   GRASS   GRASS   GRASS   GRASS   GRASS   GRASS   GRASS   GRASS
      Row 6:          GRASS  GRASS   GRASS   GRASS   GRASS   GRASS   GRASS   GRASS   GRASS   GRASS
      Row 7:          GRASS  GRASS   GRASS   GRASS   GRASS   GRASS   GRASS   GRASS   URBAN   URBAN
      Row 8:          GRASS  GRASS   GRASS   GRASS   GRASS   GRASS   GRASS   GRASS   URBAN   URBAN
      Row 9 (south):  GRASS  GRASS   GRASS   GRASS   GRASS   GRASS   GRASS   GRASS   GRASS   GRASS

      Fire starts at (7, 2) — south-west grassland.
      Wind blows from the south-west (225°) → pushes fire north-east.
    """
    grid = TerrainGrid(rows=10, cols=10)

    # ── North: lake (north-west corner) ───────────────────────────
    # Water cells are impassable — fire cannot spread here.
    for r in range(2):
        grid.get_cell(r, 0).terrain_type = TerrainType.WATER
        grid.get_cell(r, 0).vegetation = 0.0

    # ── North: forest (rows 0–3) ─────────────────────────────────
    # Dense vegetation, moderate fuel moisture.
    for r in range(4):
        for c in range(10):
            cell = grid.get_cell(r, c)
            if cell.terrain_type == TerrainType.WATER:
                continue  # don't overwrite the lake
            cell.terrain_type = TerrainType.FOREST
            cell.vegetation = 0.85
            cell.fuel_moisture = 0.3

    # ── Middle: rock ridge (row 4) ────────────────────────────────
    # Acts as a natural firebreak.
    # Two scrub cells at (4,6) and (4,7) create a gap in the ridge
    # where fire MIGHT jump through — this is the decision point.
    for c in range(10):
        cell = grid.get_cell(4, c)
        if c in (6, 7):
            # Gap in the ridge — scrub, not rock.
            # Fire can potentially cross here.
            cell.terrain_type = TerrainType.SCRUB
            cell.vegetation = 0.4
            cell.fuel_moisture = 0.2
        else:
            cell.terrain_type = TerrainType.ROCK
            cell.vegetation = 0.0

    # ── South: grassland (rows 5–9) ──────────────────────────────
    # Medium vegetation, low moisture (dry season).
    # Fire spreads fast here.
    for r in range(5, 10):
        for c in range(10):
            cell = grid.get_cell(r, c)
            cell.terrain_type = TerrainType.GRASSLAND
            cell.vegetation = 0.6
            cell.fuel_moisture = 0.15

    # ── South-east: urban area ────────────────────────────────────
    # Buildings — low vegetation but high asset value.
    # The agent should flag these as needing protection.
    for r in (7, 8):
        for c in (8, 9):
            cell = grid.get_cell(r, c)
            cell.terrain_type = TerrainType.URBAN
            cell.vegetation = 0.1
            cell.fuel_moisture = 0.05  # very dry (building materials)

    # ── Add some slope to the north half ──────────────────────────
    # Fire spreads faster uphill.  The north side of the ridge
    # has a slight uphill slope, making it harder for fire to
    # cross the ridge from south to north.
    for r in range(4):
        for c in range(10):
            grid.get_cell(r, c).slope = 5.0  # slight uphill

    # ── Weather: hot, dry, south-west wind ────────────────────────
    weather = WeatherState(
        temperature_c=38.0,         # hot
        humidity_pct=12.0,          # very dry
        wind_speed_mps=8.0,         # moderate-strong wind
        wind_direction_deg=225.0,   # from south-west → pushes fire north-east
        pressure_hpa=1008.0,        # slightly low pressure
    )

    # ── Fire spread module ────────────────────────────────────────
    fire_spread = FireSpreadHeuristic(
        base_probability=0.15,
        burn_duration_ticks=5,
    )

    # ── Build engine ──────────────────────────────────────────────
    engine = WorldEngine(
        grid=grid,
        weather=weather,
        fire_spread=fire_spread,
    )

    # ── Initial ignition ──────────────────────────────────────────
    # Fire starts in the south-west grassland.
    engine.inject_ignition(row=7, col=2, intensity=0.8)

    return engine
