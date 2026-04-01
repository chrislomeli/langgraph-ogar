"""
ogar.world.scenarios

Factory functions that configure named simulation scenarios.

Each scenario function returns a fully configured WorldEngine
ready to tick.  Scenarios encode:
  - Grid size and terrain layout
  - Initial fire ignition points
  - Starting weather conditions
  - Which fire spread module to use

Usage:
  from ogar.world.scenarios.wildfire_basic import create_basic_wildfire
  engine = create_basic_wildfire()
  engine.run(ticks=60)
"""
