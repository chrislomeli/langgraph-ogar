"""
ogar.sensors.world_sensors

Concrete sensors that sample from a WorldEngine.

How these work
──────────────
Each sensor holds a reference to a WorldEngine.  When read() is
called, the sensor queries the engine's current grid or weather
state and returns a domain-specific payload dict.

The base class (SensorBase) handles wrapping that payload in a
SensorEvent envelope, applying failure modes, and tracking ticks.
These subclasses only implement read() — the part that knows what
to sample and how to add noise.

This is the correct relationship:
  WorldEngine (ground truth) → Sensor.read() (sample + noise) → SensorEvent envelope

The agent sees SensorEvents.  It never sees the WorldEngine.
The gap between ground truth and noisy sensor reading is where
interesting agent reasoning happens.

Noise model
───────────
Each sensor adds Gaussian noise to its readings.  The noise_std
parameter controls how much noise is added.  Set to 0.0 for
perfect readings (useful for debugging).

Real sensors also have systematic biases (calibration drift,
offset errors) — the FailureMode.DRIFT mode in SensorBase
handles this at the base class level.

Sensor types implemented here
──────────────────────────────
  TemperatureSensor    : reads ambient temperature from weather +
                         fire intensity from nearby cells
  HumiditySensor       : reads humidity from weather
  WindSensor           : reads wind speed and direction from weather
  SmokeSensor          : reads particulate density based on nearby
                         fire intensity and wind
  BarometricSensor     : reads atmospheric pressure from weather
  ThermalCameraSensor  : reads a heat grid from a region of the terrain

All readings use units and ranges based on real-world sensor
specifications (see inline comments for references).
"""

from __future__ import annotations

import math
import random
from typing import Any, Dict, List, Optional

from ogar.sensors.base import SensorBase
from ogar.world.engine import WorldEngine
from ogar.world.grid import FireState


# ── Temperature sensor ────────────────────────────────────────────────────────

class TemperatureSensor(SensorBase):
    """
    Reads ambient temperature from the weather state.

    If the sensor is positioned near burning cells, the temperature
    reading is boosted to reflect radiant heat.  This creates the
    signal that the agent uses to detect nearby fire.

    Real-world reference:
      RAWS (Remote Automatic Weather Stations) report temperature
      every 10-60 minutes in °C.  Typical range: -10 to 55°C.
      Fire proximity can raise readings to 80°C+ at close range.
    """

    source_type = "temperature"

    def __init__(
        self,
        *,
        engine: WorldEngine,
        grid_row: int,
        grid_col: int,
        noise_std: float = 0.5,
        **kwargs,
    ) -> None:
        """
        Parameters
        ──────────
        engine    : the WorldEngine to sample from
        grid_row  : the row position of this sensor on the grid
        grid_col  : the column position of this sensor on the grid
        noise_std : standard deviation of Gaussian noise added to readings
        **kwargs  : passed to SensorBase (source_id, cluster_id, metadata)
        """
        super().__init__(**kwargs)
        self._engine = engine
        self._grid_row = grid_row
        self._grid_col = grid_col
        self._noise_std = noise_std

    def read(self) -> Dict[str, Any]:
        """
        Return a temperature reading in Celsius.

        The reading is:
          ambient temperature from weather
          + heat contribution from nearby burning cells
          + Gaussian noise
        """
        # Start with the global ambient temperature.
        base_temp = self._engine.weather.temperature_c

        # Add heat contribution from nearby burning cells.
        # Fire radiates heat — closer cells contribute more.
        heat_boost = 0.0
        for nr, nc in self._engine.grid.neighbors(self._grid_row, self._grid_col):
            neighbor = self._engine.grid.get_cell(nr, nc)
            if neighbor.fire_state == FireState.BURNING:
                # Intensity 1.0 at an adjacent cell adds ~15°C.
                # This is a PLACEHOLDER — real radiant heat follows
                # an inverse-square law with distance and depends on
                # flame height, fuel type, etc.
                heat_boost += neighbor.fire_intensity * 15.0

        # Also check the cell the sensor sits on.
        own_cell = self._engine.grid.get_cell(self._grid_row, self._grid_col)
        if own_cell.fire_state == FireState.BURNING:
            heat_boost += own_cell.fire_intensity * 40.0

        # Add noise.
        noise = random.gauss(0, self._noise_std)

        celsius = base_temp + heat_boost + noise
        return {
            "celsius": round(celsius, 1),
            "unit": "C",
        }


# ── Humidity sensor ───────────────────────────────────────────────────────────

class HumiditySensor(SensorBase):
    """
    Reads relative humidity from the weather state.

    Real-world reference:
      Standard hygrometers report 0–100% relative humidity.
      In fire-prone regions, values below 20% are considered
      extreme fire danger.  Readings are typically every 10-60 min.
    """

    source_type = "humidity"

    def __init__(
        self,
        *,
        engine: WorldEngine,
        noise_std: float = 1.0,
        **kwargs,
    ) -> None:
        super().__init__(**kwargs)
        self._engine = engine
        self._noise_std = noise_std

    def read(self) -> Dict[str, Any]:
        humidity = self._engine.weather.humidity_pct + random.gauss(0, self._noise_std)
        # Clamp to physical bounds.
        humidity = max(0.0, min(100.0, humidity))
        return {
            "relative_humidity_pct": round(humidity, 1),
            "unit": "%",
        }


# ── Wind sensor ───────────────────────────────────────────────────────────────

class WindSensor(SensorBase):
    """
    Reads wind speed and direction from the weather state.

    Real-world reference:
      Anemometers report wind speed (m/s) and direction (compass degrees).
      Resolution varies: 0.1 m/s for speed, 1° for direction.
      Gusts are short-duration spikes above sustained speed.
    """

    source_type = "wind"

    def __init__(
        self,
        *,
        engine: WorldEngine,
        speed_noise_std: float = 0.3,
        direction_noise_std: float = 3.0,
        **kwargs,
    ) -> None:
        super().__init__(**kwargs)
        self._engine = engine
        self._speed_noise_std = speed_noise_std
        self._direction_noise_std = direction_noise_std

    def read(self) -> Dict[str, Any]:
        speed = self._engine.weather.wind_speed_mps + random.gauss(0, self._speed_noise_std)
        speed = max(0.0, speed)

        direction = self._engine.weather.wind_direction_deg + random.gauss(0, self._direction_noise_std)
        direction = direction % 360.0

        return {
            "speed_mps": round(speed, 1),
            "direction_deg": round(direction, 1),
            "unit": "m/s",
        }


# ── Smoke sensor ──────────────────────────────────────────────────────────────

class SmokeSensor(SensorBase):
    """
    Reads particulate density (PM2.5) based on nearby fire and wind.

    The smoke reading is derived from:
      - Total fire intensity in nearby cells
      - Wind: smoke travels downwind, so sensors downwind of fire
        see higher readings
      - Distance: closer fires contribute more

    This is synthetic — real smoke dispersion depends on atmospheric
    stability, terrain channeling, and particle physics.  This is a
    PLACEHOLDER that produces plausible directional patterns.

    Real-world reference:
      PM2.5 sensors report in µg/m³.
      Clean air: 0–12 µg/m³
      Moderate:  12–35 µg/m³
      Unhealthy: 35–150 µg/m³
      Hazardous: 150+ µg/m³
      Near active wildfire: 500+ µg/m³
    """

    source_type = "smoke"

    def __init__(
        self,
        *,
        engine: WorldEngine,
        grid_row: int,
        grid_col: int,
        noise_std: float = 2.0,
        **kwargs,
    ) -> None:
        super().__init__(**kwargs)
        self._engine = engine
        self._grid_row = grid_row
        self._grid_col = grid_col
        self._noise_std = noise_std

    def read(self) -> Dict[str, Any]:
        """
        Compute a PM2.5 reading based on fire proximity and wind.

        For each burning cell, compute:
          contribution = intensity * distance_falloff * wind_alignment

        Sum all contributions, add baseline and noise.
        """
        baseline_pm25 = 5.0  # clean air background

        wind_row, wind_col = self._engine.weather.wind_vector()
        wind_speed = self._engine.weather.wind_speed_mps

        total_smoke = 0.0
        for r in range(self._engine.grid.rows):
            for c in range(self._engine.grid.cols):
                cell = self._engine.grid.get_cell(r, c)
                if cell.fire_state != FireState.BURNING:
                    continue

                # Distance from fire cell to this sensor.
                dr = self._grid_row - r
                dc = self._grid_col - c
                dist = math.sqrt(dr * dr + dc * dc)
                if dist == 0:
                    dist = 0.5  # sensor is ON the fire cell

                # Distance falloff: smoke dissipates with distance.
                # PLACEHOLDER — real dispersion follows Gaussian plume model.
                distance_factor = 1.0 / (1.0 + dist)

                # Wind alignment: is this sensor downwind of the fire?
                # Dot product of wind direction and fire-to-sensor direction.
                if dist > 0:
                    dir_r = dr / dist
                    dir_c = dc / dist
                    # Wind pushes smoke in the wind direction.
                    # If sensor is downwind of fire, dot > 0.
                    dot = wind_row * dir_r + wind_col * dir_c
                    wind_factor = max(0.1, 0.5 + dot * 0.5)
                else:
                    wind_factor = 1.0

                # Scale by wind speed: stronger wind carries more smoke.
                speed_factor = 1.0 + min(wind_speed / 15.0, 1.0)

                contribution = cell.fire_intensity * distance_factor * wind_factor * speed_factor * 80.0
                total_smoke += contribution

        pm25 = baseline_pm25 + total_smoke + random.gauss(0, self._noise_std)
        pm25 = max(0.0, pm25)

        return {
            "pm25_ugm3": round(pm25, 1),
            "unit": "µg/m³",
        }


# ── Barometric pressure sensor ───────────────────────────────────────────────

class BarometricSensor(SensorBase):
    """
    Reads atmospheric pressure from the weather state.

    Real-world reference:
      Standard barometers report in hPa (hectopascals).
      Normal range: 980–1040 hPa.
      Low pressure (< 1005 hPa) often indicates storm systems.
    """

    source_type = "barometric_pressure"

    def __init__(
        self,
        *,
        engine: WorldEngine,
        noise_std: float = 0.3,
        **kwargs,
    ) -> None:
        super().__init__(**kwargs)
        self._engine = engine
        self._noise_std = noise_std

    def read(self) -> Dict[str, Any]:
        pressure = self._engine.weather.pressure_hpa + random.gauss(0, self._noise_std)
        return {
            "pressure_hpa": round(pressure, 1),
            "unit": "hPa",
        }


# ── Thermal camera sensor ────────────────────────────────────────────────────

class ThermalCameraSensor(SensorBase):
    """
    Reads a heat map (temperature grid) from a region of the terrain.

    Unlike a single-point temperature sensor, a thermal camera
    covers a rectangular area of the grid and returns a 2D array
    of temperature values.

    This creates a richer signal for the agent — it can see spatial
    patterns (hotspot shape, fire front geometry) rather than just
    a single number.

    Real-world reference:
      FLIR-style thermal cameras produce pixel grids of temperature.
      Resolution varies.  In wildfire monitoring, each pixel might
      represent 10–100m depending on altitude and optics.
      Temperature range: ambient to 800°C+ at flame surface.
    """

    source_type = "thermal_camera"

    def __init__(
        self,
        *,
        engine: WorldEngine,
        top_row: int,
        left_col: int,
        view_rows: int,
        view_cols: int,
        noise_std: float = 1.0,
        **kwargs,
    ) -> None:
        """
        Parameters
        ──────────
        engine    : the WorldEngine to sample from
        top_row   : the top-left row of the camera's field of view
        left_col  : the top-left column of the camera's field of view
        view_rows : how many rows the camera covers
        view_cols : how many columns the camera covers
        noise_std : standard deviation of Gaussian noise per pixel
        """
        super().__init__(**kwargs)
        self._engine = engine
        self._top_row = top_row
        self._left_col = left_col
        self._view_rows = view_rows
        self._view_cols = view_cols
        self._noise_std = noise_std

    def read(self) -> Dict[str, Any]:
        """
        Return a 2D grid of temperature values (Celsius) for the
        camera's field of view.

        Each cell's temperature is:
          ambient + (fire_intensity * heat_contribution) + noise

        Burning cells show as hot spots.  The agent can use the
        spatial pattern to identify fire fronts and spread direction.
        """
        ambient = self._engine.weather.temperature_c
        heat_grid: List[List[float]] = []

        for r in range(self._top_row, self._top_row + self._view_rows):
            row_temps: List[float] = []
            for c in range(self._left_col, self._left_col + self._view_cols):
                # Check bounds — camera FOV may extend beyond grid edge.
                if 0 <= r < self._engine.grid.rows and 0 <= c < self._engine.grid.cols:
                    cell = self._engine.grid.get_cell(r, c)
                    # Burning cells add significant heat.
                    # Intensity 1.0 adds ~200°C — visible as a clear hot spot.
                    fire_heat = cell.fire_intensity * 200.0
                    temp = ambient + fire_heat + random.gauss(0, self._noise_std)
                else:
                    # Out of bounds — return ambient (camera sees sky/edge).
                    temp = ambient + random.gauss(0, self._noise_std)
                row_temps.append(round(temp, 1))
            heat_grid.append(row_temps)

        return {
            "grid_celsius": heat_grid,
            "top_row": self._top_row,
            "left_col": self._left_col,
            "view_rows": self._view_rows,
            "view_cols": self._view_cols,
            "unit": "C",
        }
