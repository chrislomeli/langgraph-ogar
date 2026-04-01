"""
ogar.world.fire_spread

Pluggable fire spread behaviour models.

This package contains:
  interface.py  ← FireSpreadModule ABC — the contract that ALL fire
                   spread implementations must satisfy.
  heuristic.py  ← FireSpreadHeuristic — a PLACEHOLDER implementation
                   using probabilistic cellular automaton rules.

The placeholder is explicitly labeled as such.  It produces
plausible-looking fire behaviour for agent testing but does NOT
model real fire physics.  It can be replaced by:
  - A semi-empirical model (e.g. Rothermel-style rate of spread)
  - A physics-based model (e.g. computational fluid dynamics)
  - An ML-based model trained on historical fire data

Swapping is mechanical: implement the FireSpreadModule interface,
pass your new module to WorldEngine.  No other code changes.
"""
