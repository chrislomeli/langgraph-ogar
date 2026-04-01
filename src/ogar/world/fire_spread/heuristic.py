"""
ogar.world.fire_spread.heuristic

FireSpreadHeuristic — PLACEHOLDER fire spread implementation.

╔═══════════════════════════════════════════════════════════════╗
║  THIS IS A PLACEHOLDER.                                      ║
║                                                               ║
║  It uses simplified probabilistic rules to simulate fire      ║
║  spread for R&D and agent testing.  It does NOT model real    ║
║  wildfire physics.                                            ║
║                                                               ║
║  It can be replaced with a semi-empirical model (Rothermel),  ║
║  a physics-based model, or an ML model by implementing the    ║
║  FireSpreadModule interface.                                  ║
╚═══════════════════════════════════════════════════════════════╝

How it works
────────────
This is a stochastic cellular automaton:

  For each BURNING cell:
    1. Check: has it burned long enough?  If yes → EXTINGUISHED.
    2. For each UNBURNED neighbor that is burnable:
       a. Compute spread probability from environmental factors.
       b. Roll the dice.  If probability exceeds the roll → IGNITED.

Spread probability factors
───────────────────────────
  base_probability     : starting chance of spread (tunable, default 0.15)

  wind_factor          : increases probability when wind blows FROM the
                         burning cell TOWARD the neighbor.
                         Computed using dot product of wind vector and
                         the direction from burning cell to neighbor.
                         Range: 0.5 (upwind) to 2.0 (downwind).

  slope_factor         : fire spreads faster uphill.
                         If the neighbor is uphill (positive slope),
                         probability increases.  Downhill, it decreases.
                         Range: 0.7 (downhill) to 1.5 (steep uphill).

  fuel_moisture_factor : drier fuel catches fire more easily.
                         fuel_moisture=0.0 (bone dry) → factor 1.5
                         fuel_moisture=1.0 (saturated) → factor 0.1
                         Range: 0.1 to 1.5.

  vegetation_factor    : denser vegetation = more fuel = easier spread.
                         vegetation=0.0 → factor 0.0 (can't burn)
                         vegetation=1.0 → factor 1.3
                         Range: 0.0 to 1.3.

  humidity_factor      : global humidity affects everything.
                         Low humidity → fire spreads more readily.
                         humidity=5% → factor 1.4
                         humidity=80% → factor 0.3
                         Range: 0.3 to 1.4.

Final probability = base * wind * slope * fuel_moisture * vegetation * humidity
Clamped to [0.0, 0.95] — fire should never be certain.

Burn duration
─────────────
A cell burns for a fixed number of ticks (default 5).
After that, it transitions to BURNED.  In a real model,
burn duration would depend on fuel load and intensity.
This is a placeholder — clearly labeled as such.

These factors and constants are informed by how the Rothermel
model categorises inputs (wind, slope, fuel moisture), but the
actual formula is a simple product of multipliers, not a
physics-derived rate-of-spread equation.
"""

from __future__ import annotations

import math
import random
from typing import List

from ogar.world.fire_spread.interface import (
    FireEvent,
    FireEventType,
    FireSpreadModule,
)
from ogar.world.grid import TerrainGrid
from ogar.world.weather import WeatherState


class FireSpreadHeuristic(FireSpreadModule):
    """
    Placeholder fire spread using probabilistic heuristic rules.

    See module docstring for detailed explanation of each factor.
    """

    def __init__(
        self,
        *,
        base_probability: float = 0.15,
        burn_duration_ticks: int = 5,
    ) -> None:
        """
        Parameters
        ──────────
        base_probability    : The starting probability of fire spreading
                              to any one neighbor, before environmental
                              factors are applied.  Default 0.15 (15%).
                              Increase for faster-spreading fires.

        burn_duration_ticks : How many ticks a cell burns before the
                              fire goes out (EXTINGUISHED).
                              Default 5 ticks.
                              PLACEHOLDER — a real model would compute
                              this from fuel load and intensity.
        """
        self._base_prob = base_probability
        self._burn_duration = burn_duration_ticks

    def tick_fire(
        self,
        grid: TerrainGrid,
        weather: WeatherState,
        tick: int,
    ) -> List[FireEvent]:
        """
        Compute one tick of fire spread.

        See FireSpreadModule.tick_fire() for the interface contract.
        See module docstring for how the heuristic works.
        """
        events: List[FireEvent] = []

        # Pre-compute values we'll use for every burning cell.
        wind_row, wind_col = weather.wind_vector()
        humidity_factor = self._compute_humidity_factor(weather.humidity_pct)

        # Get all currently burning cells.
        burning = grid.burning_cells()

        # Track which cells we've already decided to ignite THIS tick,
        # so we don't ignite the same cell twice from two different
        # burning neighbors.
        newly_ignited: set[tuple[int, int]] = set()

        for row, col in burning:
            cell = grid.get_cell(row, col)

            # ── Check burn duration ───────────────────────────────
            # Has this cell been burning long enough?
            # If so, extinguish it (fuel exhausted).
            if cell.fire_start_tick is not None:
                ticks_burning = tick - cell.fire_start_tick
                if ticks_burning >= self._burn_duration:
                    events.append(FireEvent(
                        row=row,
                        col=col,
                        event_type=FireEventType.EXTINGUISHED,
                        intensity=0.0,
                    ))
                    continue  # don't spread from a cell that just burned out

            # ── Try to spread to each burnable neighbor ───────────
            for nr, nc in grid.neighbors(row, col):
                # Skip if already ignited this tick (by another neighbor)
                if (nr, nc) in newly_ignited:
                    continue

                neighbor = grid.get_cell(nr, nc)
                if not neighbor.is_burnable:
                    continue

                # Compute spread probability for this specific neighbor.
                prob = self._spread_probability(
                    row, col, nr, nc,
                    cell, neighbor,
                    wind_row, wind_col,
                    weather.wind_speed_mps,
                    humidity_factor,
                )

                # Roll the dice.
                if random.random() < prob:
                    # Intensity of the new fire is based on the parent's
                    # intensity scaled by vegetation density.
                    # PLACEHOLDER — a real model would compute this
                    # from fuel energy content.
                    new_intensity = min(1.0, cell.fire_intensity * neighbor.vegetation * 1.2)
                    new_intensity = max(0.1, new_intensity)  # minimum visible fire

                    events.append(FireEvent(
                        row=nr,
                        col=nc,
                        event_type=FireEventType.IGNITED,
                        intensity=new_intensity,
                    ))
                    newly_ignited.add((nr, nc))

        return events

    def _spread_probability(
        self,
        from_row: int, from_col: int,
        to_row: int, to_col: int,
        from_cell,
        to_cell,
        wind_row: float, wind_col: float,
        wind_speed: float,
        humidity_factor: float,
    ) -> float:
        """
        Compute the probability that fire spreads from one cell to a neighbor.

        This is the core heuristic — a product of independent factors,
        each modulating the base probability.

        All factors and their ranges are documented in the module docstring.
        """
        # ── Wind factor ───────────────────────────────────────────
        # Direction from burning cell to neighbor, as a unit vector.
        dr = to_row - from_row
        dc = to_col - from_col
        dist = math.sqrt(dr * dr + dc * dc)
        if dist > 0:
            dr /= dist
            dc /= dist

        # Dot product: how well does the wind align with the spread direction?
        # +1.0 = perfectly downwind, -1.0 = perfectly upwind
        dot = wind_row * dr + wind_col * dc

        # Map dot product [-1, 1] to wind_factor [0.5, 2.0]
        # and scale by wind speed (stronger wind = bigger effect).
        # At wind_speed=0, wind doesn't matter (factor=1.0).
        wind_influence = dot * min(wind_speed / 10.0, 1.0)  # cap at 10 m/s
        wind_factor = 1.0 + wind_influence * 0.5             # range: 0.5 to 1.5
        # Further boost for strong downwind
        if dot > 0.5 and wind_speed > 8.0:
            wind_factor *= 1.3                                # up to ~2.0

        # ── Slope factor ──────────────────────────────────────────
        # Fire spreads faster uphill because hot air rises and
        # pre-heats the fuel above.
        # to_cell.slope is in degrees.  Positive = uphill.
        # PLACEHOLDER: in a real model, slope is relative to the
        # direction of spread.  Here we just use the cell's slope value.
        slope_deg = to_cell.slope
        if slope_deg > 0:
            slope_factor = 1.0 + min(slope_deg / 30.0, 0.5)  # up to 1.5
        else:
            slope_factor = 1.0 + max(slope_deg / 30.0, -0.3)  # down to 0.7

        # ── Fuel moisture factor ──────────────────────────────────
        # Dry fuel ignites easily.  Wet fuel resists.
        # fuel_moisture 0.0 → 1.5, fuel_moisture 1.0 → 0.1
        moisture = to_cell.fuel_moisture
        fuel_moisture_factor = 1.5 - moisture * 1.4

        # ── Vegetation density factor ─────────────────────────────
        # More vegetation = more fuel = easier spread.
        # vegetation 0.0 → 0.0 (can't burn), 1.0 → 1.3
        vegetation_factor = to_cell.vegetation * 1.3

        # ── Diagonal penalty ──────────────────────────────────────
        # Diagonal neighbors are farther away (√2 vs 1).
        # Reduce probability slightly for diagonal spread.
        is_diagonal = (from_row != to_row) and (from_col != to_col)
        diagonal_factor = 0.8 if is_diagonal else 1.0

        # ── Combine all factors ───────────────────────────────────
        prob = (
            self._base_prob
            * wind_factor
            * slope_factor
            * fuel_moisture_factor
            * vegetation_factor
            * humidity_factor
            * diagonal_factor
        )

        # Clamp to [0.0, 0.95] — fire should never be guaranteed.
        return max(0.0, min(0.95, prob))

    @staticmethod
    def _compute_humidity_factor(humidity_pct: float) -> float:
        """
        Convert global humidity percentage to a spread multiplier.

        Low humidity → fire spreads more easily (factor > 1.0).
        High humidity → fire is suppressed (factor < 1.0).

        humidity  5% → 1.4
        humidity 50% → 0.85
        humidity 80% → 0.3

        Linear interpolation between these anchor points.
        """
        # Normalise humidity to [0, 1] range
        h = max(0.0, min(100.0, humidity_pct)) / 100.0
        # Linear map: h=0 → 1.5, h=1.0 → 0.2
        return 1.5 - h * 1.3
