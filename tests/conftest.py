"""
Pytest configuration and shared fixtures.

Fixtures provide reusable test setup/teardown.
"""

import pytest

from symbolic_music.domain import (
    MeterChange,
    MeterMap,
    RationalTime,
    TempoChange,
    TempoMap,
    TempoValue,
    TimeSignature,
)


# =============================================================================
# Domain Fixtures (no external dependencies)
# =============================================================================

@pytest.fixture
def quarter_note() -> RationalTime:
    """A quarter note duration."""
    return RationalTime(n=1, d=4)


@pytest.fixture
def half_note() -> RationalTime:
    """A half note duration."""
    return RationalTime(n=1, d=2)


@pytest.fixture
def time_sig_4_4() -> TimeSignature:
    """Common time (4/4)."""
    return TimeSignature(num=4, den=4)


@pytest.fixture
def time_sig_3_4() -> TimeSignature:
    """Waltz time (3/4)."""
    return TimeSignature(num=3, den=4)


@pytest.fixture
def simple_meter_map(time_sig_4_4) -> MeterMap:
    """Single 4/4 meter map starting at bar 1."""
    return MeterMap(changes=(
        MeterChange(at_bar=1, ts=time_sig_4_4),
    ))


@pytest.fixture
def simple_tempo_map() -> TempoMap:
    """120 BPM tempo map."""
    return TempoMap(changes=(
        TempoChange(
            at_bar=1,
            at_beat=1,
            tempo=TempoValue(bpm=RationalTime(n=120, d=1), beat_unit_den=4),
        ),
    ))


# =============================================================================
# Database Fixtures (require running Memgraph)
# =============================================================================

@pytest.fixture(scope="session")
def db_writer():
    """
    GraphMusicWriter connected to test database.
    
    Requires: docker-compose up -d
    
    Clears all data before and after test session.
    """
    from symbolic_music.persistence import GraphMusicWriter
    
    writer = GraphMusicWriter()
    
    # Clear before tests
    try:
        writer.db.execute("MATCH (n) DETACH DELETE n")
    except Exception as e:
        pytest.skip(f"Memgraph not available: {e}")
    
    yield writer
    
    # Clear after tests
    writer.db.execute("MATCH (n) DETACH DELETE n")


@pytest.fixture(scope="session")
def db_reader():
    """GraphMusicReader connected to test database."""
    from symbolic_music.persistence import GraphMusicReader
    
    return GraphMusicReader()


@pytest.fixture
def clean_db(db_writer):
    """
    Provides a clean database for each test.
    
    Use this when tests need isolation from each other.
    """
    db_writer.db.execute("MATCH (n) DETACH DELETE n")
    yield db_writer
    db_writer.db.execute("MATCH (n) DETACH DELETE n")
