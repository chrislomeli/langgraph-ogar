"""
ogar.world.fire_spread.interface

FireSpreadModule — the abstract contract for fire behaviour.

Why this interface exists
──────────────────────────
Fire behaviour is the part of the simulation most likely to be
replaced.  The initial implementation is a simple heuristic.
Later, someone might want:
  - A Rothermel-style rate-of-spread model
  - A cellular automaton tuned to real fire data
  - An ML model that predicts spread from satellite imagery

By defining the interface cleanly, all fire spread implementations
are interchangeable.  The WorldEngine calls tick_fire() and gets
back a list of state changes.  It doesn't care how those changes
were computed.

Interface contract
───────────────────
tick_fire() receives:
  - grid     : the TerrainGrid (read cell states, fire intensity, fuel)
  - weather  : the WeatherState (wind, humidity, temperature)
  - tick     : the current simulation tick number

tick_fire() returns:
  - A list of FireEvent objects describing what changed this tick

FireEvent is a lightweight dataclass that records:
  - What happened (IGNITED, INTENSIFIED, EXTINGUISHED)
  - Where it happened (row, col)
  - New intensity value

The WorldEngine applies these events to the grid after calling
tick_fire().  This separation means the fire spread module never
mutates the grid directly — the engine is always in control of
state changes, which makes debugging and logging straightforward.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import List

from ogar.world.grid import TerrainGrid
from ogar.world.weather import WeatherState


# ── Fire event types ──────────────────────────────────────────────────────────

class FireEventType(str, Enum):
    """What happened to a cell this tick."""
    IGNITED      = "IGNITED"       # cell caught fire from a neighbor
    INTENSIFIED  = "INTENSIFIED"   # already burning, intensity changed
    EXTINGUISHED = "EXTINGUISHED"  # fire burned out (fuel exhausted)


@dataclass
class FireEvent:
    """
    A single change to a cell's fire state, produced by the fire spread module.

    These are descriptive, not prescriptive — the WorldEngine reads them
    and applies the changes to the grid.  The fire spread module does
    not mutate the grid directly.

    row, col     : which cell changed
    event_type   : what happened (see FireEventType)
    intensity    : new intensity value (0.0 for EXTINGUISHED)
    """
    row: int
    col: int
    event_type: FireEventType
    intensity: float


# ── Abstract interface ────────────────────────────────────────────────────────

class FireSpreadModule(ABC):
    """
    Abstract contract for fire behaviour.

    To implement a new fire model:
      1. Subclass FireSpreadModule
      2. Implement tick_fire()
      3. Pass your instance to WorldEngine

    That's it.  Everything else stays the same.

    The module should be stateless between ticks — all state lives
    in the grid and weather.  This makes it safe to swap modules
    mid-simulation if needed (e.g. for A/B testing different models).
    """

    @abstractmethod
    def tick_fire(
        self,
        grid: TerrainGrid,
        weather: WeatherState,
        tick: int,
    ) -> List[FireEvent]:
        """
        Compute fire state changes for one simulation tick.

        Parameters
        ──────────
        grid    : the current terrain grid (read-only — do NOT mutate)
        weather : the current weather conditions
        tick    : the current simulation tick number

        Returns
        ───────
        A list of FireEvent objects describing what changed.
        May be empty if nothing happened this tick (e.g. no fire on grid).

        Implementation notes
        ─────────────────────
        - Read grid.burning_cells() to find active fires.
        - For each burning cell, check neighbors via grid.neighbors().
        - Use weather.wind_vector() and weather.humidity_pct to modulate
          spread probability.
        - Use cell.vegetation, cell.fuel_moisture, cell.slope to modulate
          per-cell spread probability.
        - Return FireEvent(IGNITED, ...) for newly ignited neighbors.
        - Return FireEvent(EXTINGUISHED, ...) for cells that burned out.
        - Do NOT modify the grid — return events and let the engine apply them.
        """
        ...
