# Symbolic Music Persistence Layer

This document explains the data layer implementation under `src/symbolic_music/persistence/`. It covers the purpose of each module, key features, and how data flows between the domain model and Memgraph.

## High-Level Architecture

```
Domain (pure Pydantic models)
        ↓ (adapt)
Adapter — canonicalize & hash domain objects @src/symbolic_music/persistence/adapter.py
        ↓ (write)                                        ↑ (read)
Writer — issues Cypher commands to Memgraph             Reader — reconstructs domain models
@src/symbolic_music/persistence/writer.py               @src/symbolic_music/persistence/reader.py
        ↓                                                   ↑
 Memgraph graph database (content-addressed nodes & relationships)
```

### Core Responsibilities

| Module | Responsibility |
| --- | --- |
| `adapter.py` | Bidirectional conversions between domain objects and graph properties, canonical JSON for hashing, content-addressing helpers. @src/symbolic_music/persistence/adapter.py#1-120 |
| `writer.py` | Executes Cypher statements to create identities, version nodes, and relationship edges. Coordinates persistence via adapters. @src/symbolic_music/persistence/writer.py#1-200 |
| `reader.py` | Executes read queries, reconstructs domain models, caches sections, and enforces type-safe rows. @src/symbolic_music/persistence/reader.py#1-210 |
| `async_reader.py` | Async variant powered by `neo4j.AsyncGraphDatabase`, mirroring reader features for non-blocking code paths. @src/symbolic_music/persistence/async_reader.py#1-420 |
| `types.py` | `TypedDict` definitions describing the row shapes returned by Cypher queries. @src/symbolic_music/persistence/types.py#1-145 |
| `__init__.py` | Barrel exports for writers, readers, adapters, and utilities. @src/symbolic_music/persistence/__init__.py#1-44 |

## Module Details

### `adapter.py`
- Defines canonical JSON serialization to ensure deterministic SHA-256 hashes via `content_hash`. @src/symbolic_music/persistence/adapter.py#43-103
- Provides adapter classes (`RationalTimeAdapter`, `PitchAdapter`, `EventAdapter`, etc.) that translate domain objects to graph properties and vice versa. @src/symbolic_music/persistence/adapter.py#104-632
- Centralizes hashing logic for content-addressed storage so identical musical structures map to identical version nodes.

### `writer.py`
- Manages the Memgraph connection via `gqlalchemy.Memgraph`. @src/symbolic_music/persistence/writer.py#15-38
- Defines all Cypher queries for creating identities, version nodes, and relationships (events, measures, sections, meter/tempo maps, tracks, compositions). @src/symbolic_music/persistence/writer.py#54-337
- Public API includes helpers such as `create_section`, `commit_section_version`, `commit_composition_version`, etc., each relying on adapters to convert domain objects to property dictionaries. @src/symbolic_music/persistence/writer.py#275-337

### `reader.py`
- Issues read queries defined near the top of the module; each query returns canonical row shapes defined in `types.py`. @src/symbolic_music/persistence/reader.py#48-134
- `GraphMusicReader` accepts host/port plus cache settings and stores sections in a TTL cache (default: 5 minutes, 100 entries). @src/symbolic_music/persistence/reader.py#154-210
- Public methods `load_composition_by_title` and `load_composition_by_cid` hydrate full `CompositionSpec` graphs, including tracks, sections, measures, and events. @src/symbolic_music/persistence/reader.py#186-288
- Internal helpers (`_load_meter_map`, `_load_tempo_map`, `_load_track`, `_load_section`, `_load_measure`, `_build_event`) mirror the write-side adapter logic to rebuild domain objects. @src/symbolic_music/persistence/reader.py#263-420

### `async_reader.py`
- Async counterpart using `neo4j.AsyncGraphDatabase`. Implements `AsyncGraphMusicReader` with the same caching and helper structure. @src/symbolic_music/persistence/async_reader.py#180-421
- `_execute` returns typed rows (leveraging the `row_type` generic parameter) so IDEs and mypy know the exact structure coming back from the database. @src/symbolic_music/persistence/async_reader.py#198-207
- All read helpers (`_load_meter_map`, `_load_tempo_map`, etc.) are `async def` functions awaiting query execution. @src/symbolic_music/persistence/async_reader.py#287-421

### `types.py`
- Documents row schemas such as `CompositionRow`, `TrackRow`, `SectionRow`, and `EventRow`. This ensures that both sync and async readers consume strongly-typed dictionaries, enabling better tooling and reducing runtime mistakes. @src/symbolic_music/persistence/types.py#13-145

### `__init__.py`
- Exposes `GraphMusicWriter`, `GraphMusicReader`, `AsyncGraphMusicReader`, all adapter classes, and `content_hash` for convenient imports. @src/symbolic_music/persistence/__init__.py#11-44

## Data Flow (Write → Read)

1. **Domain to Graph**
   - Callers construct domain objects (`CompositionSpec`, `SectionSpec`, etc.).
   - `GraphMusicWriter` uses adapters to produce deterministic property dicts and relationships, then executes Cypher commands to store them. @src/symbolic_music/persistence/writer.py#275-337
2. **Graph Storage**
   - Nodes are content-addressed using SHA-256 of canonical JSON, ensuring deduplication for identical musical content. @src/symbolic_music/persistence/adapter.py#40-103
3. **Graph to Domain**
   - `GraphMusicReader` (or async variant) queries Memgraph, receives typed rows, reconstructs domain models, and caches sections for repeated access. @src/symbolic_music/persistence/reader.py#186-420

## Testing Strategy

- `tests/test_persistence.py` contains integration tests that spin up Memgraph (via Docker) and assert identity creation, version commits, and roundtrip fidelity. @tests/test_persistence.py#1-119
- Additional unit tests cover adapters (`tests/test_adapter.py`) and domain logic (`tests/test_domain.py`), ensuring the data layer’s conversions remain correct under schema changes.

## Developer Tips

- **Editable install**: run `pip install -e .` from repo root to make `symbolic_music` importable.
- **Memgraph setup**: `docker-compose up -d` launches Memgraph at `127.0.0.1:7687`.
- **Schema**: apply constraints with `python -m symbolic_music.persistence.schema.setup` before running persistence tests.
- **Async usage**: use `AsyncGraphMusicReader` within `async with` contexts for FastAPI or other async frameworks.

This overview should provide enough context for contributors focusing on the persistence/data layer. For broader architecture, refer to `SETUP.md` and top-level README.
