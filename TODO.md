# Symbolic Music - Improvement Roadmap

## Completed

| # | Area | Description | Status |
|---|------|-------------|--------|
| 1 | Package Structure | Refactor into `src/symbolic_music/` with domain, persistence, rendering subpackages | ✅ Done |
| 2 | Test Suite | Unit tests for domain/adapter, integration tests for persistence | ✅ Done |
| 3 | Type Hints | TypedDict for database row results | ✅ Done |
| 4 | Caching | TTL cache for section reads | ✅ Done |
| 5 | Async Support | AsyncGraphMusicReader using neo4j AsyncGraphDatabase | ✅ Done |

## Pending Improvements

| # | Area | Description | Priority | Status |
|---|------|-------------|----------|--------|
| 6 | Async Writer | Add AsyncGraphMusicWriter for non-blocking writes | Medium | ✅ Done |
| 7 | Error Hierarchy | Richer domain exceptions (NotFoundError, ValidationError, PersistenceError) | Low | ⬜ |
| 8 | Logging | Structured logging with configurable levels | Low | ⬜ |
| 9 | Connection Pooling | Configure connection pool for high-throughput scenarios | Low | ⬜ |
| 10 | Batch Operations | Bulk write/read operations for large compositions | Medium | ⬜ |
| 11 | Query Optimization | Profile and optimize Cypher queries for large graphs | Low | ⬜ |
| 12 | Schema Migrations | Version-aware schema migration tooling | Low | ⬜ |
| 13 | CLI Tool | Command-line interface for common operations | Medium | ⬜ |
| 14 | Documentation | API docs with Sphinx/MkDocs | Medium | 🟡 Partial (data layer docs done) |
| 15 | CI/CD | GitHub Actions for tests, linting, type checking | Medium | ⬜ |

## Notes

- **Async**: Both reader and writer now have async support via `AsyncGraphMusicReader` and `AsyncGraphMusicWriter`.
- **Caching**: Current TTL cache is in-memory only. Consider Redis for distributed deployments.
- **Type Hints**: Core types are covered. Could add `Protocol` classes for adapter interfaces.
