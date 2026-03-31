"""
Graph database write operations.

Responsibilities:
- Execute Cypher queries for creating nodes and relationships
- Manage Memgraph connection
- Coordinate persistence using adapter for conversions
- Handle version node creation and identity relationships
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional

from gqlalchemy import Memgraph

from symbolic_music.domain import (
    CompositionSpec,
    MeasureSpec,
    MeterMap,
    SectionSpec,
    TempoMap,
    TrackSpec,
)
from symbolic_music.persistence.adapter import (
    CompositionAdapter,
    EventAdapter,
    MeasureAdapter,
    MeterMapAdapter,
    PitchAdapter,
    SectionAdapter,
    TempoMapAdapter,
    TrackAdapter,
    content_hash,
)


# =============================================================================
# Helpers
# =============================================================================

def _now_iso() -> str:
    """Current timestamp in ISO format."""
    return datetime.now(timezone.utc).isoformat()


def _uuid() -> str:
    """Generate UUID for version nodes."""
    return str(uuid.uuid4())


# =============================================================================
# Cypher Queries
# =============================================================================

CQL_CREATE_SECTION = """
MERGE (s:Section {sid: $sid})
ON CREATE SET s.name = $name, s.created_at = $created_at
RETURN s.sid AS sid
"""

CQL_CREATE_COMPOSITION = """
MERGE (c:Composition {cid: $cid})
ON CREATE SET c.title = $title, c.created_at = $created_at
RETURN c.cid AS cid
"""

CQL_CREATE_TRACK = """
MERGE (t:Track {tid: $tid})
ON CREATE SET t.created_at = $created_at, t.name = $name
RETURN t.tid AS tid
"""

CQL_CREATE_PITCH = """
MERGE (p:Pitch {content_hash: $content_hash})
ON CREATE SET p.pitch_id = $pitch_id,
              p.midi = $midi,
              p.cents_n = $cents_n,
              p.cents_d = $cents_d,
              p.spelling_hint = $spelling_hint,
              p.created_at = $created_at
RETURN p.pitch_id AS pitch_id, p.content_hash AS content_hash
"""

CQL_CREATE_ARTICULATION = """
MERGE (a:Articulation {name: $name})
RETURN a.name AS name
"""

CQL_CREATE_EVENT_VERSION = """
MERGE (e:EventVersion {content_hash: $content_hash})
ON CREATE SET e.evid = $evid,
              e.created_at = $created_at,
              e.schema_version = $schema_version,
              e.kind = $kind,
              e.offset_n = $offset_n, e.offset_d = $offset_d,
              e.dur_n = $dur_n, e.dur_d = $dur_d,
              e.midi = $midi,
              e.midi_min = $midi_min,
              e.midi_max = $midi_max,
              e.velocity = $velocity,
              e.tie = $tie,
              e.meta_type = $meta_type
RETURN e.evid AS evid, e.content_hash AS content_hash
"""

CQL_CREATE_MEASURE_VERSION = """
MERGE (m:MeasureVersion {content_hash: $content_hash})
ON CREATE SET m.mvid = $mvid,
              m.created_at = $created_at,
              m.schema_version = $schema_version,
              m.local_ts_num = $local_ts_num,
              m.local_ts_den = $local_ts_den
RETURN m.mvid AS mvid, m.content_hash AS content_hash
"""

CQL_CREATE_SECTION_VERSION = """
MERGE (sv:SectionVersion {content_hash: $content_hash})
ON CREATE SET sv.svid = $svid,
              sv.sid = $sid,
              sv.created_at = $created_at,
              sv.schema_version = $schema_version,
              sv.name = $name
RETURN sv.svid AS svid, sv.content_hash AS content_hash
"""

CQL_CREATE_METERMAP_VERSION = """
MERGE (mm:MeterMapVersion {content_hash: $content_hash})
ON CREATE SET mm.meter_vid = $meter_vid,
              mm.created_at = $created_at,
              mm.schema_version = $schema_version
RETURN mm.meter_vid AS meter_vid, mm.content_hash AS content_hash
"""

CQL_CREATE_TEMPOMAP_VERSION = """
MERGE (tm:TempoMapVersion {content_hash: $content_hash})
ON CREATE SET tm.tempo_vid = $tempo_vid,
              tm.created_at = $created_at,
              tm.schema_version = $schema_version
RETURN tm.tempo_vid AS tempo_vid, tm.content_hash AS content_hash
"""

CQL_CREATE_TRACK_VERSION = """
MERGE (tv:TrackVersion {content_hash: $content_hash})
ON CREATE SET tv.tvid = $tvid,
              tv.tid = $tid,
              tv.created_at = $created_at,
              tv.schema_version = $schema_version,
              tv.track_id = $track_id,
              tv.name = $name,
              tv.instrument_hint = $instrument_hint,
              tv.midi_channel = $midi_channel,
              tv.clef = $clef,
              tv.transposition_semitones = $transposition_semitones
RETURN tv.tvid AS tvid, tv.content_hash AS content_hash
"""

CQL_CREATE_COMPOSITION_VERSION = """
MERGE (cv:CompositionVersion {content_hash: $content_hash})
ON CREATE SET cv.cvid = $cvid,
              cv.cid = $cid,
              cv.created_at = $created_at,
              cv.schema_version = $schema_version,
              cv.title = $title
RETURN cv.cvid AS cvid, cv.content_hash AS content_hash
"""

# Relationship creation

CQL_LINK_EVENT_PITCH = """
MATCH (e:EventVersion {evid: $evid}), (p:Pitch {content_hash: $pitch_hash})
MERGE (e)-[:HAS_PITCH {i: $i}]->(p)
"""

CQL_LINK_EVENT_ARTICULATION = """
MATCH (e:EventVersion {evid: $evid})
MERGE (a:Articulation {name: $artic_name})
MERGE (e)-[:HAS_ARTICULATION {i: $i}]->(a)
"""

CQL_LINK_EVENT_LYRIC = """
MATCH (e:EventVersion {evid: $evid})
MERGE (l:Lyric {text: $lyric_text})
MERGE (e)-[:HAS_LYRIC]->(l)
"""

CQL_LINK_MEASURE_EVENT = """
MATCH (m:MeasureVersion {mvid: $mvid}), (e:EventVersion {evid: $evid})
MERGE (m)-[:HAS_EVENT {i: $i}]->(e)
"""

CQL_LINK_SECTION_MEASURE = """
MATCH (sv:SectionVersion {svid: $svid}), (m:MeasureVersion {mvid: $mvid})
MERGE (sv)-[:HAS_MEASURE {i: $i}]->(m)
"""

CQL_LINK_METERMAP_CHANGE = """
MATCH (mm:MeterMapVersion {meter_vid: $meter_vid})
MERGE (mm)-[:HAS_CHANGE {
    at_bar: $at_bar,
    ts_num: $ts_num,
    ts_den: $ts_den,
    i: $i
}]->(:TimeSignature {num: $ts_num, den: $ts_den})
"""

CQL_LINK_TEMPOMAP_CHANGE = """
MATCH (tm:TempoMapVersion {tempo_vid: $tempo_vid})
MERGE (tm)-[:HAS_CHANGE {
    at_bar: $at_bar,
    at_beat: $at_beat,
    bpm_n: $bpm_n,
    bpm_d: $bpm_d,
    beat_unit_den: $beat_unit_den,
    i: $i
}]->(:TempoValue {bpm_n: $bpm_n, bpm_d: $bpm_d, beat_unit_den: $beat_unit_den})
"""

CQL_LINK_TRACK_PLACEMENT = """
MATCH (tv:TrackVersion {tvid: $tvid}), (sv:SectionVersion {svid: $svid})
MERGE (tv)-[r:USES_SECTION {start_bar: $start_bar, ordinal: $ordinal}]->(sv)
SET r.repeats = $repeats,
    r.transpose_semitones = $transpose_semitones,
    r.gain_db = $gain_db
SET r.role = CASE WHEN $role IS NOT NULL THEN $role ELSE r.role END
"""

CQL_LINK_COMPOSITION_TIMELINE = """
MATCH (cv:CompositionVersion {cvid: $cvid})
MATCH (mm:MeterMapVersion {meter_vid: $meter_vid})
MATCH (tm:TempoMapVersion {tempo_vid: $tempo_vid})
MERGE (cv)-[:USES_METERMAP]->(mm)
MERGE (cv)-[:USES_TEMPOMAP]->(tm)
"""

CQL_LINK_COMPOSITION_TRACK = """
MATCH (cv:CompositionVersion {cvid: $cvid}), (tv:TrackVersion {tvid: $tvid})
MERGE (cv)-[:HAS_TRACK]->(tv)
"""

CQL_UPDATE_LATEST = """
MATCH (i:%(IDENT_LABEL)s {%(IDENT_KEY)s: $ident_id})
OPTIONAL MATCH (i)-[old:LATEST]->()
DELETE old
WITH i
MATCH (v:%(VER_LABEL)s {%(VER_KEY)s: $ver_id})
MERGE (i)-[:LATEST]->(v)
"""


# =============================================================================
# Writer Class
# =============================================================================

class GraphMusicWriter:
    """
    Graph database write operations.
    
    Philosophy:
    - Every Cypher query is explicit and readable
    - Content-addressed versioning prevents duplicates
    - Identity nodes provide stable handles
    - All conversions delegated to adapter
    """
    
    def __init__(self, host: str = "127.0.0.1", port: int = 7687):
        self.db = Memgraph(host=host, port=port)
    
    # =========================================================================
    # Identity Node Creation
    # =========================================================================
    
    def create_section(self, name: str, *, sid: Optional[str] = None) -> str:
        """Create Section identity node."""
        sid = sid or _uuid()
        rows = list(self.db.execute_and_fetch(CQL_CREATE_SECTION, {
            "sid": sid,
            "name": name,
            "created_at": _now_iso(),
        }))
        return rows[0]["sid"]
    
    def create_composition(self, title: str, *, cid: Optional[str] = None) -> str:
        """Create Composition identity node."""
        cid = cid or _uuid()
        rows = list(self.db.execute_and_fetch(CQL_CREATE_COMPOSITION, {
            "cid": cid,
            "title": title,
            "created_at": _now_iso(),
        }))
        return rows[0]["cid"]
    
    def create_track(self, name: str, *, tid: Optional[str] = None) -> str:
        """Create Track identity node."""
        tid = tid or _uuid()
        rows = list(self.db.execute_and_fetch(CQL_CREATE_TRACK, {
            "tid": tid,
            "name": name,
            "created_at": _now_iso(),
        }))
        return rows[0]["tid"]
    
    # =========================================================================
    # Timeline Versions
    # =========================================================================
    
    def commit_meter_map(
        self,
        meter_map: MeterMap,
        *,
        schema_version: int = 1,
    ) -> str:
        """Commit MeterMap as content-addressed version node."""
        h = MeterMapAdapter.compute_hash(meter_map)
        meter_vid = _uuid()
        
        rows = list(self.db.execute_and_fetch(CQL_CREATE_METERMAP_VERSION, {
            "content_hash": h,
            "meter_vid": meter_vid,
            "created_at": _now_iso(),
            "schema_version": schema_version,
        }))
        
        meter_vid = rows[0]["meter_vid"]
        
        for i, change in enumerate(meter_map.changes):
            self.db.execute(CQL_LINK_METERMAP_CHANGE, {
                "meter_vid": meter_vid,
                "at_bar": change.at_bar,
                "ts_num": change.ts.num,
                "ts_den": change.ts.den,
                "i": i,
            })
        
        return meter_vid
    
    def commit_tempo_map(
        self,
        tempo_map: TempoMap,
        *,
        schema_version: int = 1,
    ) -> str:
        """Commit TempoMap as content-addressed version node."""
        h = TempoMapAdapter.compute_hash(tempo_map)
        tempo_vid = _uuid()
        
        rows = list(self.db.execute_and_fetch(CQL_CREATE_TEMPOMAP_VERSION, {
            "content_hash": h,
            "tempo_vid": tempo_vid,
            "created_at": _now_iso(),
            "schema_version": schema_version,
        }))
        
        tempo_vid = rows[0]["tempo_vid"]
        
        for i, change in enumerate(tempo_map.changes):
            self.db.execute(CQL_LINK_TEMPOMAP_CHANGE, {
                "tempo_vid": tempo_vid,
                "at_bar": change.at_bar,
                "at_beat": change.at_beat,
                "bpm_n": change.tempo.bpm.n,
                "bpm_d": change.tempo.bpm.d,
                "beat_unit_den": change.tempo.beat_unit_den,
                "i": i,
            })
        
        return tempo_vid
    
    # =========================================================================
    # Event Version
    # =========================================================================
    
    def _commit_pitch_by_props(self, props: dict) -> str:
        """Helper: commit pitch from pre-computed properties."""
        rows = list(self.db.execute_and_fetch(CQL_CREATE_PITCH, {
            "content_hash": props["content_hash"],
            "pitch_id": _uuid(),
            "midi": props["midi"],
            "cents_n": props["cents_n"],
            "cents_d": props["cents_d"],
            "spelling_hint": props.get("spelling_hint"),
            "created_at": _now_iso(),
        }))
        return rows[0]["content_hash"]
    
    def commit_event(self, event, *, schema_version: int = 1) -> str:
        """Commit Event as content-addressed version node."""
        props = EventAdapter.to_properties(event)
        h = content_hash(EventAdapter.to_canonical(event))
        evid = _uuid()
        
        rows = list(self.db.execute_and_fetch(CQL_CREATE_EVENT_VERSION, {
            "content_hash": h,
            "evid": evid,
            "created_at": _now_iso(),
            "schema_version": schema_version,
            "kind": props["kind"],
            "offset_n": props["offset_n"],
            "offset_d": props["offset_d"],
            "dur_n": props["dur_n"],
            "dur_d": props["dur_d"],
            "midi": props.get("midi"),
            "midi_min": props.get("midi_min"),
            "midi_max": props.get("midi_max"),
            "velocity": props.get("velocity"),
            "tie": props.get("tie"),
            "meta_type": props.get("meta_type"),
        }))
        
        evid = rows[0]["evid"]
        
        rels = EventAdapter.to_relationships(event)
        for rel_type, target_props, rel_props in rels:
            if rel_type == "HAS_PITCH":
                pitch_hash = target_props["content_hash"]
                self._commit_pitch_by_props(target_props)
                self.db.execute(CQL_LINK_EVENT_PITCH, {
                    "evid": evid,
                    "pitch_hash": pitch_hash,
                    "i": rel_props["i"],
                })
            elif rel_type == "HAS_ARTICULATION":
                self.db.execute(CQL_LINK_EVENT_ARTICULATION, {
                    "evid": evid,
                    "artic_name": target_props["name"],
                    "i": rel_props["i"],
                })
            elif rel_type == "HAS_LYRIC":
                self.db.execute(CQL_LINK_EVENT_LYRIC, {
                    "evid": evid,
                    "lyric_text": target_props["text"],
                })
        
        return evid
    
    # =========================================================================
    # Measure Version
    # =========================================================================
    
    def commit_measure(
        self,
        measure: MeasureSpec,
        *,
        schema_version: int = 1,
    ) -> str:
        """Commit Measure as content-addressed version node."""
        props = MeasureAdapter.to_properties(measure)
        h = MeasureAdapter.compute_hash(measure)
        mvid = _uuid()
        
        rows = list(self.db.execute_and_fetch(CQL_CREATE_MEASURE_VERSION, {
            "content_hash": h,
            "mvid": mvid,
            "created_at": _now_iso(),
            "schema_version": schema_version,
            "local_ts_num": props.get("local_ts_num"),
            "local_ts_den": props.get("local_ts_den"),
        }))
        
        mvid = rows[0]["mvid"]
        
        for i, event in enumerate(measure.events):
            evid = self.commit_event(event, schema_version=schema_version)
            self.db.execute(CQL_LINK_MEASURE_EVENT, {
                "mvid": mvid,
                "evid": evid,
                "i": i,
            })
        
        return mvid
    
    # =========================================================================
    # Section Version
    # =========================================================================
    
    def commit_section_version(
        self,
        sid: str,
        spec: SectionSpec,
        *,
        schema_version: int = 1,
    ) -> str:
        """Commit SectionVersion."""
        props = SectionAdapter.to_properties(spec)
        h = SectionAdapter.compute_hash(spec)
        svid = _uuid()
        
        rows = list(self.db.execute_and_fetch(CQL_CREATE_SECTION_VERSION, {
            "content_hash": h,
            "svid": svid,
            "sid": sid,
            "created_at": _now_iso(),
            "schema_version": schema_version,
            "name": props["name"],
        }))
        
        svid = rows[0]["svid"]
        
        for i, measure in enumerate(spec.measures):
            mvid = self.commit_measure(measure, schema_version=schema_version)
            self.db.execute(CQL_LINK_SECTION_MEASURE, {
                "svid": svid,
                "mvid": mvid,
                "i": i,
            })
        
        self.db.execute(
            CQL_UPDATE_LATEST % {
                "IDENT_LABEL": "Section",
                "IDENT_KEY": "sid",
                "VER_LABEL": "SectionVersion",
                "VER_KEY": "svid",
            },
            {"ident_id": sid, "ver_id": svid},
        )
        
        return svid
    
    # =========================================================================
    # Track Version
    # =========================================================================
    
    def commit_track_version(
        self,
        tid: str,
        spec: TrackSpec,
        *,
        schema_version: int = 1,
    ) -> str:
        """Commit TrackVersion."""
        props = TrackAdapter.to_properties(spec)
        h = TrackAdapter.compute_hash(spec)
        tvid = _uuid()
        
        rows = list(self.db.execute_and_fetch(CQL_CREATE_TRACK_VERSION, {
            "content_hash": h,
            "tvid": tvid,
            "tid": tid,
            "created_at": _now_iso(),
            "schema_version": schema_version,
            "track_id": props["track_id"],
            "name": props["name"],
            "instrument_hint": props.get("instrument_hint"),
            "midi_channel": props.get("midi_channel"),
            "clef": props.get("clef"),
            "transposition_semitones": props["transposition_semitones"],
        }))
        
        tvid = rows[0]["tvid"]
        
        for ordinal, placement in enumerate(spec.placements):
            self.db.execute(CQL_LINK_TRACK_PLACEMENT, {
                "tvid": tvid,
                "svid": placement.section_version_id,
                "start_bar": placement.start_bar,
                "ordinal": ordinal,
                "repeats": placement.repeats,
                "transpose_semitones": placement.transpose_semitones,
                "role": placement.role,
                "gain_db": placement.gain_db,
            })
        
        self.db.execute(
            CQL_UPDATE_LATEST % {
                "IDENT_LABEL": "Track",
                "IDENT_KEY": "tid",
                "VER_LABEL": "TrackVersion",
                "VER_KEY": "tvid",
            },
            {"ident_id": tid, "ver_id": tvid},
        )
        
        return tvid
    
    # =========================================================================
    # Composition Version
    # =========================================================================
    
    def commit_composition_version(
        self,
        cid: str,
        spec: CompositionSpec,
        *,
        schema_version: int = 1,
    ) -> str:
        """Commit CompositionVersion."""
        meter_vid = self.commit_meter_map(spec.meter_map, schema_version=schema_version)
        tempo_vid = self.commit_tempo_map(spec.tempo_map, schema_version=schema_version)
        
        props = CompositionAdapter.to_properties(spec)
        h = CompositionAdapter.compute_hash(spec)
        cvid = _uuid()
        
        rows = list(self.db.execute_and_fetch(CQL_CREATE_COMPOSITION_VERSION, {
            "content_hash": h,
            "cvid": cvid,
            "cid": cid,
            "created_at": _now_iso(),
            "schema_version": schema_version,
            "title": props["title"],
        }))
        
        cvid = rows[0]["cvid"]
        
        self.db.execute(CQL_LINK_COMPOSITION_TIMELINE, {
            "cvid": cvid,
            "meter_vid": meter_vid,
            "tempo_vid": tempo_vid,
        })
        
        for track_spec in spec.tracks:
            self.create_track(name=track_spec.config.name, tid=track_spec.track_id)
            tvid = self.commit_track_version(
                tid=track_spec.track_id,
                spec=track_spec,
                schema_version=schema_version,
            )
            self.db.execute(CQL_LINK_COMPOSITION_TRACK, {
                "cvid": cvid,
                "tvid": tvid,
            })
        
        self.db.execute(
            CQL_UPDATE_LATEST % {
                "IDENT_LABEL": "Composition",
                "IDENT_KEY": "cid",
                "VER_LABEL": "CompositionVersion",
                "VER_KEY": "cvid",
            },
            {"ident_id": cid, "ver_id": cvid},
        )
        
        return cvid


# Backwards compatibility alias
GraphMusicStore = GraphMusicWriter
