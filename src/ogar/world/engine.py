"""
ogar.world.engine

WorldEngine — the simulation tick loop that coordinates everything.

What this does
──────────────
The WorldEngine is the central coordinator.  Each tick:

  1. Weather evolves (temperature drifts, wind shifts, humidity adjusts).
  2. Fire spread module runs (computes which cells ignite or extinguish).
  3. Fire events are applied to the grid.
  4. Ground truth snapshot is recorded.

After a tick, any sensors attached to the engine can sample from
the current grid and weather state to produce SensorEvent envelopes.

The engine does NOT:
  - Know about Kafka, LangGraph, or agents.
  - Publish events to any bus.
  - Run sensors automatically.

Sensors are separate objects that hold a reference to the engine
and call engine.grid / engine.weather when they need a reading.
This keeps the engine pure simulation and the sensors pure sampling.

Ground truth
────────────
After every tick, the engine records a GroundTruthSnapshot:
  - Which cells are burning, at what intensity
  - Weather conditions at that tick
  - A summary (counts of unburned/burning/burned cells)

This is the "answer key" for evaluating agent decisions.
The agent never sees ground truth — it only sees sensor readings.
After a scenario completes, you compare what the agent thought
was happening to what was actually happening.

Reproducibility
───────────────
Set a random seed before running the engine to get deterministic
results.  This is essential for:
  - Debugging agent behaviour on a specific scenario
  - Comparing two agent implementations on identical conditions
  - Regression testing

  import random
  random.seed(42)
  engine = WorldEngine(...)
  engine.run(ticks=60)
  # Same sequence every time.

Usage
─────
  from ogar.world.engine import WorldEngine
  from ogar.world.grid import TerrainGrid
  from ogar.world.weather import WeatherState
  from ogar.world.fire_spread.heuristic import FireSpreadHeuristic

  grid = TerrainGrid(rows=10, cols=10)
  grid.get_cell(5, 5).ignite(tick=0, intensity=0.8)

  weather = WeatherState(temperature_c=35, humidity_pct=15, wind_speed_mps=8)
  fire_module = FireSpreadHeuristic()

  engine = WorldEngine(grid=grid, weather=weather, fire_spread=fire_module)

  for _ in range(60):
      snapshot = engine.tick()
      print(snapshot.summary)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from ogar.world.fire_spread.interface import (
    FireEvent,
    FireEventType,
    FireSpreadModule,
)
from ogar.world.grid import TerrainGrid
from ogar.world.weather import WeatherState

logger = logging.getLogger(__name__)


# ── Ground truth snapshot ─────────────────────────────────────────────────────

@dataclass
class GroundTruthSnapshot:
    """
    What was actually happening in the world at a given tick.

    The agent never sees this.  It is used after the scenario for
    evaluation: "the agent said there was no fire in cluster-north,
    but the ground truth shows cells (2,3) and (2,4) were burning."

    tick              : which simulation tick this snapshot is from
    weather           : weather conditions at this tick
    burning_cells     : list of (row, col) cells currently on fire
    fire_events       : what changed this tick (ignitions, extinguishments)
    cell_summary      : count of UNBURNED / BURNING / BURNED cells
    fire_intensity_map: 2D grid of intensity values (0.0 = no fire)
    """
    tick: int
    weather: Dict[str, Any]
    burning_cells: List[tuple[int, int]]
    fire_events: List[Dict[str, Any]]
    cell_summary: Dict[str, int]
    fire_intensity_map: List[List[float]]


# ── World engine ──────────────────────────────────────────────────────────────

class WorldEngine:
    """
    The simulation coordinator.

    Holds the grid, weather, and fire spread module.
    Advances the simulation one tick at a time.
    Records ground truth for evaluation.
    """

    def __init__(
        self,
        *,
        grid: TerrainGrid,
        weather: WeatherState,
        fire_spread: FireSpreadModule,
    ) -> None:
        """
        Parameters
        ──────────
        grid        : the terrain grid (cells with vegetation, fuel, fire state)
        weather     : the starting weather conditions
        fire_spread : the pluggable fire behaviour model

        The engine takes ownership of grid and weather — it will
        mutate them on each tick.  If you need the original state,
        take a snapshot before running.
        """
        self.grid = grid
        self.weather = weather
        self._fire_spread = fire_spread

        # Current simulation tick.  Starts at 0, incremented by tick().
        self._tick: int = 0

        # History of ground truth snapshots, one per tick.
        # Access via self.history or self.get_snapshot(tick).
        self.history: List[GroundTruthSnapshot] = []

    @property
    def current_tick(self) -> int:
        """The current simulation tick (0-based, incremented after each tick)."""
        return self._tick

    def tick(self) -> GroundTruthSnapshot:
        """
        Advance the simulation by one step.

        Order of operations:
          1. Weather evolves
          2. Fire spread module computes events
          3. Events are applied to the grid
          4. Ground truth snapshot is recorded
          5. Tick counter advances

        Returns the ground truth snapshot for this tick.
        """
        # ── 1. Evolve weather ─────────────────────────────────────
        self.weather.tick()

        # ── 2. Compute fire spread ────────────────────────────────
        fire_events: List[FireEvent] = self._fire_spread.tick_fire(
            grid=self.grid,
            weather=self.weather,
            tick=self._tick,
        )

        # ── 3. Apply fire events to the grid ──────────────────────
        # The fire spread module returns events but does NOT mutate
        # the grid.  We apply them here so the engine controls all
        # state changes.
        for event in fire_events:
            cell = self.grid.get_cell(event.row, event.col)

            if event.event_type == FireEventType.IGNITED:
                cell.ignite(tick=self._tick, intensity=event.intensity)
                logger.debug(
                    "Tick %d: cell (%d,%d) IGNITED at intensity %.2f",
                    self._tick, event.row, event.col, event.intensity,
                )

            elif event.event_type == FireEventType.EXTINGUISHED:
                cell.extinguish()
                logger.debug(
                    "Tick %d: cell (%d,%d) EXTINGUISHED",
                    self._tick, event.row, event.col,
                )

            elif event.event_type == FireEventType.INTENSIFIED:
                cell.fire_intensity = max(0.0, min(1.0, event.intensity))

        # ── 4. Record ground truth ────────────────────────────────
        snapshot = GroundTruthSnapshot(
            tick=self._tick,
            weather=self.weather.to_dict(),
            burning_cells=self.grid.burning_cells(),
            fire_events=[
                {
                    "row": e.row,
                    "col": e.col,
                    "type": e.event_type.value,
                    "intensity": round(e.intensity, 3),
                }
                for e in fire_events
            ],
            cell_summary=self.grid.summary(),
            fire_intensity_map=self.grid.fire_intensity_grid(),
        )
        self.history.append(snapshot)

        # Log a summary line for visibility during demos.
        summary = snapshot.cell_summary
        logger.info(
            "Tick %03d | burning=%d unburned=%d burned=%d | events=%d | %s",
            self._tick,
            summary.get("BURNING", 0),
            summary.get("UNBURNED", 0),
            summary.get("BURNED", 0),
            len(fire_events),
            self.weather,
        )

        # ── 5. Advance tick ───────────────────────────────────────
        self._tick += 1

        return snapshot

    def run(self, ticks: int) -> List[GroundTruthSnapshot]:
        """
        Run the simulation for a fixed number of ticks.

        Convenience method for scenarios that run to completion
        rather than being driven tick-by-tick by an event loop.

        Returns the list of ground truth snapshots generated.
        """
        snapshots = []
        for _ in range(ticks):
            snapshots.append(self.tick())
        return snapshots

    def get_snapshot(self, tick: int) -> Optional[GroundTruthSnapshot]:
        """
        Retrieve the ground truth snapshot for a specific tick.

        Returns None if the tick hasn't been simulated yet.
        """
        if 0 <= tick < len(self.history):
            return self.history[tick]
        return None

    def inject_ignition(self, row: int, col: int, intensity: float = 0.7) -> None:
        """
        Manually ignite a cell.

        Used by scenario scripts to start fires at specific locations
        and times during the simulation.

        Parameters
        ──────────
        row, col  : which cell to ignite
        intensity : initial fire intensity (0.0–1.0)

        Does nothing if the cell is not burnable (rock, water,
        already burning or burned).
        """
        cell = self.grid.get_cell(row, col)
        if cell.is_burnable:
            cell.ignite(tick=self._tick, intensity=intensity)
            logger.info(
                "Injected ignition at (%d,%d) intensity=%.2f tick=%d",
                row, col, intensity, self._tick,
            )
        else:
            logger.warning(
                "Cannot ignite cell (%d,%d) — terrain=%s fire_state=%s",
                row, col, cell.terrain_type.value, cell.fire_state.value,
            )
