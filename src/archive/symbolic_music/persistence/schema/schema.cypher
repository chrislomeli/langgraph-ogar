// schema.cypher
// Graph schema for symbolic music storage.
// Run once on a fresh Memgraph instance.

// =============================================================================
// Identity Nodes (stable handles)
// =============================================================================

CREATE CONSTRAINT ON (n:Section) ASSERT n.sid IS UNIQUE;
CREATE CONSTRAINT ON (n:Composition) ASSERT n.cid IS UNIQUE;
CREATE CONSTRAINT ON (n:Track) ASSERT n.tid IS UNIQUE;

// =============================================================================
// Version Nodes (immutable, content-addressed)
// =============================================================================

CREATE CONSTRAINT ON (n:SectionVersion) ASSERT n.svid IS UNIQUE;
CREATE CONSTRAINT ON (n:MeasureVersion) ASSERT n.mvid IS UNIQUE;
CREATE CONSTRAINT ON (n:EventVersion) ASSERT n.evid IS UNIQUE;
CREATE CONSTRAINT ON (n:CompositionVersion) ASSERT n.cvid IS UNIQUE;
CREATE CONSTRAINT ON (n:TrackVersion) ASSERT n.tvid IS UNIQUE;
CREATE CONSTRAINT ON (n:MeterMapVersion) ASSERT n.meter_vid IS UNIQUE;
CREATE CONSTRAINT ON (n:TempoMapVersion) ASSERT n.tempo_vid IS UNIQUE;

// Content hash uniqueness (deduplication)
CREATE CONSTRAINT ON (n:SectionVersion) ASSERT n.content_hash IS UNIQUE;
CREATE CONSTRAINT ON (n:MeasureVersion) ASSERT n.content_hash IS UNIQUE;
CREATE CONSTRAINT ON (n:EventVersion) ASSERT n.content_hash IS UNIQUE;
CREATE CONSTRAINT ON (n:CompositionVersion) ASSERT n.content_hash IS UNIQUE;
CREATE CONSTRAINT ON (n:TrackVersion) ASSERT n.content_hash IS UNIQUE;
CREATE CONSTRAINT ON (n:MeterMapVersion) ASSERT n.content_hash IS UNIQUE;
CREATE CONSTRAINT ON (n:TempoMapVersion) ASSERT n.content_hash IS UNIQUE;
CREATE CONSTRAINT ON (n:Pitch) ASSERT n.content_hash IS UNIQUE;

// =============================================================================
// Indexes for Query Performance
// =============================================================================

CREATE INDEX ON :Section(sid);
CREATE INDEX ON :Composition(cid);
CREATE INDEX ON :Track(tid);

CREATE INDEX ON :SectionVersion(sid);
CREATE INDEX ON :SectionVersion(content_hash);

CREATE INDEX ON :CompositionVersion(cid);
CREATE INDEX ON :CompositionVersion(content_hash);

CREATE INDEX ON :MeterMapVersion(content_hash);
CREATE INDEX ON :TempoMapVersion(content_hash);

CREATE INDEX ON :TrackVersion(tid);
CREATE INDEX ON :TrackVersion(content_hash);

CREATE INDEX ON :Pitch(midi);
CREATE INDEX ON :Pitch(content_hash);

// Event indexes for musical queries
CREATE INDEX ON :EventVersion(kind);
CREATE INDEX ON :EventVersion(midi);
CREATE INDEX ON :EventVersion(midi_min);
CREATE INDEX ON :EventVersion(midi_max);
