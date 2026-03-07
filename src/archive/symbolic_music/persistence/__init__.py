"""
Persistence layer for symbolic music graph database.

This module handles all Memgraph interactions:
- Writing compositions to the graph (writer)
- Reading compositions from the graph (reader, async_reader)
- Converting domain objects to/from graph format (adapter)
- Type definitions for database rows (types)
"""

from symbolic_music.persistence.adapter import (
    CompositionAdapter,
    EventAdapter,
    MeasureAdapter,
    MeterMapAdapter,
    PitchAdapter,
    RationalTimeAdapter,
    SectionAdapter,
    TempoMapAdapter,
    TimeSignatureAdapter,
    TrackAdapter,
    content_hash,
)
from symbolic_music.persistence.async_reader import AsyncGraphMusicReader
from symbolic_music.persistence.async_writer import AsyncGraphMusicWriter
from symbolic_music.persistence.reader import GraphMusicReader
from symbolic_music.persistence.writer import GraphMusicWriter

__all__ = [
    # Main classes
    "GraphMusicWriter",
    "GraphMusicReader",
    "AsyncGraphMusicWriter",
    "AsyncGraphMusicReader",
    # Adapters
    "RationalTimeAdapter",
    "PitchAdapter",
    "TimeSignatureAdapter",
    "EventAdapter",
    "MeasureAdapter",
    "SectionAdapter",
    "MeterMapAdapter",
    "TempoMapAdapter",
    "TrackAdapter",
    "CompositionAdapter",
    # Utilities
    "content_hash",
]
