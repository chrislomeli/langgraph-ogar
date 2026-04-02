# Tutorial Part 1: Understanding the World Engine

## What is the World Engine?

The **World Engine** is a wildfire simulator that creates a fake world for your AI agents to practice on. Think of it like a video game level, but instead of a player controlling a character, you have AI agents trying to detect and respond to wildfires.

### The Big Picture

```
┌─────────────────────────────────────────────────────────────┐
│  World Engine (the "game")                                  │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐  │
│  │   Terrain    │    │   Weather    │    │ Fire Spread  │  │
│  │   Grid       │    │   State      │    │   Rules      │  │
│  │  (the map)   │    │ (temp, wind) │    │ (physics)    │  │
│  └──────────────┘    └──────────────┘    └──────────────┘  │
│                                                              │
│  Every "tick" (like a game frame):                          │
│    1. Weather changes a little (wind shifts, temp drifts)   │
│    2. Fire spreads to new cells (or existing fires die out) │
│    3. A "ground truth snapshot" is saved (the answer key)   │
└─────────────────────────────────────────────────────────────┘
                            ↓
                    ┌───────────────┐
                    │   Sensors     │  ← Sample the world
                    │ (thermometer, │    (noisy, incomplete)
                    │  smoke, etc.) │
                    └───────────────┘
                            ↓
                    ┌───────────────┐
                    │  AI Agents    │  ← Try to figure out
                    │               │    what's happening
                    └───────────────┘
```

**Key insight:** The AI agents never see the "ground truth." They only see sensor readings, which are noisy and incomplete. After the simulation, you compare what the agents *thought* was happening to what *actually* happened.

---

## The Three Core Components

### 1. **Terrain Grid** — The Map

A 2D grid of cells, like a chessboard. Each cell is a small patch of land (imagine 100m × 100m).

**What each cell tracks:**
- **Terrain type**: Forest, grassland, rock, water, or urban
- **Vegetation**: How much burnable stuff is there (0.0 = bare rock, 1.0 = dense forest)
- **Fuel moisture**: How wet the fuel is (0.0 = bone dry, 1.0 = soaking wet)
- **Slope**: Is it flat, uphill, or downhill?
- **Fire state**: UNBURNED, BURNING, or BURNED
- **Fire intensity**: How hot the fire is (0.0–1.0)

**Example:**
```python
from ogar.world.grid import TerrainGrid, TerrainType

# Create a 10×10 grid
grid = TerrainGrid(rows=10, cols=10)

# Set cell (5, 5) to be forest
cell = grid.get_cell(5, 5)
cell.terrain_type = TerrainType.FOREST
cell.vegetation = 0.8      # Dense forest
cell.fuel_moisture = 0.3   # Fairly dry

# Start a fire there
cell.ignite(tick=0, intensity=0.7)
```

**Coordinates:**
- `(row, col)` where `(0, 0)` is the **north-west corner**
- Row 0 = north edge, increasing row = moving south
- Col 0 = west edge, increasing col = moving east

---

### 2. **Weather State** — Environmental Conditions

Weather affects how fire spreads. Hot, dry, windy conditions = fast fire spread.

**What it tracks:**
- **Temperature** (°C)
- **Humidity** (%)
- **Wind speed** (m/s)
- **Wind direction** (compass degrees: 0° = north, 90° = east, 180° = south, 270° = west)
- **Barometric pressure** (hPa)

**Example:**
```python
from ogar.world.weather import WeatherState

# Hot, dry, windy day — perfect for wildfires
weather = WeatherState(
    temperature_c=35,      # Hot
    humidity_pct=15,       # Very dry
    wind_speed_mps=8,      # Strong wind
    wind_direction_deg=225 # Blowing from the south-west
)
```

**Weather evolves over time:**
Each tick, the weather drifts slightly (temperature goes up/down, wind shifts direction). This is controlled by a `drift_rate` parameter.

---

### 3. **Fire Spread Module** — The Physics

This is the "game engine" that decides which cells catch fire each tick.

**How it works (simplified):**
1. For each BURNING cell:
   - Has it been burning long enough? → If yes, mark it BURNED (fire dies out)
   - For each UNBURNED neighbor:
     - Calculate spread probability based on:
       - **Wind**: Fire spreads faster downwind
       - **Slope**: Fire spreads faster uphill
       - **Fuel moisture**: Drier fuel catches easier
       - **Vegetation**: More vegetation = more fuel
       - **Humidity**: Low humidity = easier spread
     - Roll the dice: if random() < probability → neighbor catches fire

**Example spread probability calculation:**
```
Base probability: 0.15
× Wind factor (downwind): 2.0
× Slope factor (uphill): 1.3
× Fuel moisture factor (dry): 1.4
× Vegetation factor (dense): 1.2
× Humidity factor (low): 1.3
─────────────────────────────
= 0.15 × 2.0 × 1.3 × 1.4 × 1.2 × 1.3 = 0.94

→ 94% chance this cell catches fire this tick
```

**Important:** This is a **placeholder** model. It's good enough for testing AI agents, but it's not real wildfire physics. You can swap it out for a real model (like Rothermel) by implementing the `FireSpreadModule` interface.

---

## Putting It All Together: The World Engine

The `WorldEngine` coordinates everything. Each tick:

1. **Weather evolves** (temperature drifts, wind shifts)
2. **Fire spread module runs** (computes which cells ignite or extinguish)
3. **Fire events are applied** to the grid
4. **Ground truth snapshot is saved** (the answer key)

**Example:**
```python
from ogar.world.engine import WorldEngine
from ogar.world.grid import TerrainGrid
from ogar.world.weather import WeatherState
from ogar.world.fire_spread.heuristic import FireSpreadHeuristic

# 1. Create the terrain
grid = TerrainGrid(rows=10, cols=10)
grid.get_cell(5, 5).ignite(tick=0, intensity=0.8)  # Start a fire

# 2. Set the weather
weather = WeatherState(temperature_c=35, humidity_pct=15, wind_speed_mps=8)

# 3. Choose a fire spread model
fire_module = FireSpreadHeuristic()

# 4. Create the engine
engine = WorldEngine(grid=grid, weather=weather, fire_spread=fire_module)

# 5. Run the simulation
for tick in range(60):
    snapshot = engine.tick()
    print(f"Tick {tick}: {snapshot.summary['burning_cells']} cells burning")
```

**Output:**
```
Tick 0: 1 cells burning
Tick 1: 2 cells burning
Tick 2: 4 cells burning
Tick 3: 7 cells burning
...
```

---

## Ground Truth vs. Sensor Readings

**Ground truth** = what's *actually* happening in the simulation.

After each tick, the engine saves a `GroundTruthSnapshot`:
- Which cells are burning
- Fire intensity in each cell
- Weather conditions
- Summary stats (how many cells unburned/burning/burned)

**The AI agents never see this.** They only see **sensor readings**, which are:
- **Noisy**: A thermometer might read 34°C when it's actually 35°C
- **Incomplete**: Sensors only cover part of the grid
- **Delayed**: Sensors might report readings from 2 ticks ago

**Why this matters:**
After the simulation, you compare:
- What the agent *thought* was happening (based on sensor readings)
- What *actually* happened (ground truth)

This is how you evaluate whether your agent is good at detecting fires.

---

## Pre-Built Scenarios

Instead of building a grid from scratch every time, you can use pre-built scenarios:

```python
from ogar.world.scenarios.wildfire_basic import create_basic_wildfire

# Get a fully configured engine ready to run
engine = create_basic_wildfire()

# The scenario includes:
#   - A 10×10 grid with forest, grassland, rock ridge, lake, and urban area
#   - Hot, dry, windy weather from the south-west
#   - One fire ignition in the south-west grassland
#   - Fire will spread north-east toward the forest and urban area

# Just tick it
for _ in range(60):
    snapshot = engine.tick()
```

**What the basic scenario looks like:**
```
Row 0 (north):  WATER  FOREST  FOREST  FOREST  ...
Row 1:          WATER  FOREST  FOREST  FOREST  ...
Row 2:          FOREST FOREST  FOREST  FOREST  ...
Row 3:          FOREST FOREST  FOREST  FOREST  ...
Row 4 (ridge):  ROCK   ROCK    ROCK    ROCK    ...  ← Firebreak
Row 5:          GRASS  GRASS   GRASS   GRASS   ...
Row 6:          GRASS  GRASS   GRASS   GRASS   ...
Row 7:          GRASS  GRASS   🔥     GRASS   ...  ← Fire starts here
Row 8:          GRASS  GRASS   GRASS   GRASS   URBAN URBAN
Row 9 (south):  GRASS  GRASS   GRASS   GRASS   ...

Wind: South-west → North-east (pushes fire toward forest and buildings)
```

---

## Reproducibility: Setting a Random Seed

Fire spread is probabilistic (dice rolls). To get the same results every time:

```python
import random
random.seed(42)

engine = create_basic_wildfire()
engine.run(ticks=60)

# Same fire spread pattern every time
```

**Why this matters:**
- **Debugging**: "Why did the agent miss the fire in cluster-north?" → Re-run with the same seed to see exactly what happened.
- **Comparison**: "Is agent v2 better than v1?" → Run both on the same scenarios.
- **Regression testing**: "Did my code change break anything?" → Run tests with fixed seeds.

---

## What the World Engine Does NOT Do

The engine is **pure simulation**. It does NOT:
- Know about Kafka, LangGraph, or agents
- Publish events to any message bus
- Run sensors automatically
- Make decisions or take actions

**Sensors are separate.** They hold a reference to the engine and sample from it:
```python
from ogar.sensors.temperature import TemperatureSensor

sensor = TemperatureSensor(
    sensor_id="temp-001",
    cluster_id="cluster-north",
    position=(2, 3),  # Grid coordinates
    engine=engine     # Reference to the world
)

# After each tick, the sensor can sample the world
reading = sensor.sample()
# → SensorEvent with temperature reading (possibly noisy)
```

---

## Next Steps

Now that you understand the World Engine, the next tutorial will cover:
- **Part 2: Sensors** — How sensors sample the world and produce events
- **Part 3: Agents** — How AI agents consume sensor events and detect anomalies
- **Part 4: The Full Pipeline** — Wiring everything together

---

## Quick Reference

### Create a simple world
```python
from ogar.world.engine import WorldEngine
from ogar.world.grid import TerrainGrid
from ogar.world.weather import WeatherState
from ogar.world.fire_spread.heuristic import FireSpreadHeuristic

grid = TerrainGrid(rows=10, cols=10)
grid.get_cell(5, 5).ignite(tick=0, intensity=0.8)

weather = WeatherState(temperature_c=35, humidity_pct=15, wind_speed_mps=8)
fire_module = FireSpreadHeuristic()

engine = WorldEngine(grid=grid, weather=weather, fire_spread=fire_module)
```

### Run the simulation
```python
# Tick once
snapshot = engine.tick()

# Run N ticks
snapshots = engine.run(ticks=60)

# Access current state
current_grid = engine.grid
current_weather = engine.weather
```

### Use a pre-built scenario
```python
from ogar.world.scenarios.wildfire_basic import create_basic_wildfire

engine = create_basic_wildfire()
engine.run(ticks=60)
```

### Set a random seed for reproducibility
```python
import random
random.seed(42)
engine = create_basic_wildfire()
```
