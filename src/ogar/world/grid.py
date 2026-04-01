"""
ogar.world.grid

TerrainGrid — the spatial model of the world.

What this is
────────────
A 2D grid of cells.  Each cell represents a small area of terrain
(think: a 100m × 100m patch of land).  The grid is the spatial
backbone of the entire simulation.

Each cell tracks:
  - terrain_type   : what kind of land (forest, grassland, rock, water, urban)
  - vegetation     : density of burnable material, 0.0–1.0
  - fuel_moisture  : how wet the fuel is, 0.0–1.0 (1.0 = saturated, 0.0 = bone dry)
  - slope          : gradient in degrees (0 = flat, positive = uphill)
  - fire_state     : one of UNBURNED, BURNING, BURNED
  - fire_intensity : 0.0–1.0 while burning (how hot the fire is in this cell)
  - fire_start_tick: which tick the fire started in this cell (None if not burning)

Why not NumPy?
──────────────
We could use NumPy arrays for the grid, but plain Python keeps the
dependency list minimal and the code readable for someone unfamiliar
with NumPy broadcasting.  The grids we're working with (10×10 to
maybe 50×50) are tiny — performance is not a concern.  If someone
wants to scale to 1000×1000, switching to NumPy is a clean refactor
because the interface (get_cell, set_cell, neighbors) stays the same.

Coordinate system
─────────────────
(row, col) where:
  row 0 is the NORTH edge of the grid
  col 0 is the WEST edge

So moving "north" means decreasing row, "east" means increasing col.
This matches how you'd print the grid top-to-bottom, left-to-right.

Wind direction is in compass degrees (0 = north, 90 = east, etc.)
and we convert to (row_delta, col_delta) when computing fire spread.
"""

from __future__ import annotations

import copy
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple


# ── Enums ─────────────────────────────────────────────────────────────────────

class TerrainType(str, Enum):
    """
    What kind of land a cell represents.

    This affects fire behaviour:
      FOREST    — high fuel load, burns slow and hot
      GRASSLAND — medium fuel, burns fast
      SCRUB     — medium fuel, moderate speed
      ROCK      — no fuel, fire cannot spread here
      WATER     — no fuel, fire cannot spread here
      URBAN     — low fuel but high asset value (buildings)

    Using str mixin so TerrainType.FOREST == "FOREST" for JSON/logging.
    """
    FOREST    = "FOREST"
    GRASSLAND = "GRASSLAND"
    SCRUB     = "SCRUB"
    ROCK      = "ROCK"
    WATER     = "WATER"
    URBAN     = "URBAN"


class FireState(str, Enum):
    """
    The fire state of a single cell.

    UNBURNED — no fire has reached this cell
    BURNING  — actively on fire
    BURNED   — fire has passed through, fuel is exhausted
    """
    UNBURNED = "UNBURNED"
    BURNING  = "BURNING"
    BURNED   = "BURNED"


# ── Cell data ─────────────────────────────────────────────────────────────────

class Cell:
    """
    One cell in the terrain grid.

    This is a mutable value object — the grid holds a 2D array of these
    and mutates them in place during each tick.

    All float fields are clamped to [0.0, 1.0] on set, so fire spread
    code doesn't need to worry about boundary checks.
    """

    __slots__ = (
        "terrain_type",
        "vegetation",
        "fuel_moisture",
        "slope",
        "fire_state",
        "fire_intensity",
        "fire_start_tick",
    )

    def __init__(
        self,
        terrain_type: TerrainType = TerrainType.GRASSLAND,
        vegetation: float = 0.5,
        fuel_moisture: float = 0.3,
        slope: float = 0.0,
    ) -> None:
        self.terrain_type = terrain_type
        self.vegetation = max(0.0, min(1.0, vegetation))
        self.fuel_moisture = max(0.0, min(1.0, fuel_moisture))
        self.slope = slope                         # degrees, can be negative (downhill)
        self.fire_state = FireState.UNBURNED
        self.fire_intensity = 0.0
        self.fire_start_tick: Optional[int] = None

    @property
    def is_burnable(self) -> bool:
        """
        Can fire spread to this cell?

        Rock, water, and already-burned cells cannot catch fire.
        Cells with zero vegetation also cannot burn.
        """
        if self.terrain_type in (TerrainType.ROCK, TerrainType.WATER):
            return False
        if self.fire_state != FireState.UNBURNED:
            return False
        if self.vegetation <= 0.0:
            return False
        return True

    def ignite(self, tick: int, intensity: float = 0.5) -> None:
        """
        Set this cell on fire.

        Parameters
        ──────────
        tick      : the simulation tick when the fire starts
        intensity : initial fire intensity, 0.0–1.0
        """
        self.fire_state = FireState.BURNING
        self.fire_intensity = max(0.0, min(1.0, intensity))
        self.fire_start_tick = tick

    def extinguish(self) -> None:
        """
        Mark this cell as burned out (fuel exhausted, fire done).

        Called by the fire spread module when burn_duration is exceeded
        or when the cell's fuel is consumed.
        """
        self.fire_state = FireState.BURNED
        self.fire_intensity = 0.0

    def to_dict(self) -> Dict[str, Any]:
        """Serialise for logging / ground truth snapshots."""
        return {
            "terrain_type": self.terrain_type.value,
            "vegetation": self.vegetation,
            "fuel_moisture": self.fuel_moisture,
            "slope": self.slope,
            "fire_state": self.fire_state.value,
            "fire_intensity": round(self.fire_intensity, 3),
            "fire_start_tick": self.fire_start_tick,
        }


# ── Terrain grid ──────────────────────────────────────────────────────────────

class TerrainGrid:
    """
    2D grid of Cell objects representing the simulated terrain.

    Usage
    ─────
      grid = TerrainGrid(rows=10, cols=10)

      # Set terrain types for a region
      grid.get_cell(0, 0).terrain_type = TerrainType.FOREST
      grid.get_cell(5, 5).vegetation = 0.9

      # Ignite a cell
      grid.get_cell(3, 3).ignite(tick=0, intensity=0.7)

      # Find neighbors of a cell (for fire spread)
      for nr, nc in grid.neighbors(3, 3):
          neighbor = grid.get_cell(nr, nc)
          if neighbor.is_burnable:
              ...
    """

    def __init__(self, rows: int, cols: int) -> None:
        """
        Create a grid of (rows × cols) cells, all initialised to grassland
        with default vegetation and moisture.

        Parameters
        ──────────
        rows : number of rows (north-south extent)
        cols : number of columns (east-west extent)
        """
        if rows < 1 or cols < 1:
            raise ValueError(f"Grid dimensions must be positive, got ({rows}, {cols})")
        self.rows = rows
        self.cols = cols
        # 2D list of Cell objects.  Accessed as self._cells[row][col].
        self._cells: List[List[Cell]] = [
            [Cell() for _ in range(cols)]
            for _ in range(rows)
        ]

    def get_cell(self, row: int, col: int) -> Cell:
        """
        Return the Cell at (row, col).

        Raises IndexError if out of bounds — this is intentional.
        Fire spread code should always check bounds via neighbors().
        """
        if not (0 <= row < self.rows and 0 <= col < self.cols):
            raise IndexError(f"Cell ({row}, {col}) out of bounds for grid ({self.rows}×{self.cols})")
        return self._cells[row][col]

    def neighbors(self, row: int, col: int) -> List[Tuple[int, int]]:
        """
        Return the (row, col) coordinates of all valid neighbors.

        Uses 8-connectivity (includes diagonals) because fire spreads
        diagonally in real life, especially with wind.

        Only returns coordinates that are within grid bounds.
        Does NOT filter by fire_state or terrain — the caller decides
        which neighbors are relevant.
        """
        result = []
        for dr in (-1, 0, 1):
            for dc in (-1, 0, 1):
                if dr == 0 and dc == 0:
                    continue  # skip self
                nr, nc = row + dr, col + dc
                if 0 <= nr < self.rows and 0 <= nc < self.cols:
                    result.append((nr, nc))
        return result

    def burning_cells(self) -> List[Tuple[int, int]]:
        """
        Return a list of (row, col) for all cells currently on fire.

        The fire spread module calls this each tick to know where
        fire is active.  Iterating the full grid is fine for small
        grids (< 100×100).  For larger grids, maintain a set of
        burning coordinates instead.
        """
        result = []
        for r in range(self.rows):
            for c in range(self.cols):
                if self._cells[r][c].fire_state == FireState.BURNING:
                    result.append((r, c))
        return result

    def fire_intensity_grid(self) -> List[List[float]]:
        """
        Return a 2D list of fire intensity values.

        This is what a thermal camera sensor would ideally see
        (before noise is added).  0.0 = no fire, 1.0 = max intensity.
        """
        return [
            [self._cells[r][c].fire_intensity for c in range(self.cols)]
            for r in range(self.rows)
        ]

    def snapshot(self) -> Dict[str, Any]:
        """
        Return a complete serialised snapshot of the grid.

        Used for ground truth logging — records the exact state of
        every cell so you can replay and evaluate agent decisions
        against what was actually happening.
        """
        return {
            "rows": self.rows,
            "cols": self.cols,
            "cells": [
                [self._cells[r][c].to_dict() for c in range(self.cols)]
                for r in range(self.rows)
            ],
        }

    def summary(self) -> Dict[str, int]:
        """
        Return a quick count of cells by fire state.

        Useful for logging and scenario scripts:
          {"UNBURNED": 85, "BURNING": 7, "BURNED": 8}
        """
        counts = {state.value: 0 for state in FireState}
        for r in range(self.rows):
            for c in range(self.cols):
                counts[self._cells[r][c].fire_state.value] += 1
        return counts
