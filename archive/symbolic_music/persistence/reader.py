"""
Graph database read operations.

Reads composition data from Memgraph and reconstructs domain objects.
This is the inverse of writer.py's write operations.
"""

from typing import Optional

from cachetools import TTLCache
from gqlalchemy import Memgraph

from symbolic_music.persistence.types import (
    CompositionRow,
    EventData,
    EventRow,
    MeasureRow,
    MeterMapChangeRow,
    PitchData,
    PlacementRow,
    SectionRow,
    TempoMapChangeRow,
    TrackRow,
)

from symbolic_music.domain import (
    ChordEvent,
    CompositionSpec,
    MeasureSpec,
    MeterChange,
    MeterMap,
    MetaEvent,
    NoteEvent,
    Pitch,
    RationalTime,
    RestEvent,
    SectionPlacement,
    SectionSpec,
    TempoChange,
    TempoMap,
    TempoValue,
    TimeSignature,
    TrackConfig,
    TrackSpec,
)


# =============================================================================
# Read Queries
# =============================================================================

CQL_GET_COMPOSITION_BY_TITLE = """
MATCH (c:Composition {title: $title})-[:LATEST]->(cv:CompositionVersion)
RETURN c.cid AS cid, c.title AS title, cv.cvid AS cvid
"""

CQL_GET_COMPOSITION_BY_CID = """
MATCH (c:Composition {cid: $cid})-[:LATEST]->(cv:CompositionVersion)
RETURN c.cid AS cid, c.title AS title, cv.cvid AS cvid
"""

CQL_GET_METER_MAP = """
MATCH (cv:CompositionVersion {cvid: $cvid})-[:USES_METERMAP]->(mm:MeterMapVersion)
OPTIONAL MATCH (mm)-[r:HAS_CHANGE]->(ts:TimeSignature)
RETURN mm.meter_vid AS meter_vid,
       r.at_bar AS at_bar,
       r.i AS i,
       ts.num AS ts_num,
       ts.den AS ts_den
ORDER BY r.i
"""

CQL_GET_TEMPO_MAP = """
MATCH (cv:CompositionVersion {cvid: $cvid})-[:USES_TEMPOMAP]->(tm:TempoMapVersion)
OPTIONAL MATCH (tm)-[r:HAS_CHANGE]->(tv:TempoValue)
RETURN tm.tempo_vid AS tempo_vid,
       r.at_bar AS at_bar,
       r.at_beat AS at_beat,
       r.i AS i,
       tv.bpm_n AS bpm_n,
       tv.bpm_d AS bpm_d,
       tv.beat_unit_den AS beat_unit_den
ORDER BY r.i
"""

CQL_GET_TRACKS = """
MATCH (cv:CompositionVersion {cvid: $cvid})-[:HAS_TRACK]->(tv:TrackVersion)
RETURN tv.tvid AS tvid,
       tv.track_id AS track_id,
       tv.name AS name,
       tv.instrument_hint AS instrument_hint,
       tv.midi_channel AS midi_channel,
       tv.clef AS clef,
       tv.transposition_semitones AS transposition_semitones
"""

CQL_GET_TRACK_PLACEMENTS = """
MATCH (tv:TrackVersion {tvid: $tvid})-[r:USES_SECTION]->(sv:SectionVersion)
RETURN sv.svid AS svid,
       r.start_bar AS start_bar,
       r.ordinal AS ordinal,
       r.repeats AS repeats,
       r.transpose_semitones AS transpose_semitones,
       r.role AS role,
       r.gain_db AS gain_db
ORDER BY r.ordinal
"""

CQL_GET_SECTION = """
MATCH (sv:SectionVersion {svid: $svid})
RETURN sv.svid AS svid, sv.name AS name
"""

CQL_GET_SECTION_MEASURES = """
MATCH (sv:SectionVersion {svid: $svid})-[r:HAS_MEASURE]->(m:MeasureVersion)
RETURN m.mvid AS mvid,
       m.local_ts_num AS local_ts_num,
       m.local_ts_den AS local_ts_den,
       r.i AS i
ORDER BY r.i
"""

CQL_GET_MEASURE_EVENTS = """
MATCH (m:MeasureVersion {mvid: $mvid})-[r:HAS_EVENT]->(e:EventVersion)
OPTIONAL MATCH (e)-[hp:HAS_PITCH]->(p:Pitch)
OPTIONAL MATCH (e)-[ha:HAS_ARTICULATION]->(a:Articulation)
OPTIONAL MATCH (e)-[:HAS_LYRIC]->(l:Lyric)
RETURN e.evid AS evid,
       e.kind AS kind,
       e.offset_n AS offset_n,
       e.offset_d AS offset_d,
       e.dur_n AS dur_n,
       e.dur_d AS dur_d,
       e.velocity AS velocity,
       e.tie AS tie,
       e.meta_type AS meta_type,
       r.i AS event_i,
       hp.i AS pitch_i,
       p.midi AS midi,
       p.cents_n AS cents_n,
       p.cents_d AS cents_d,
       p.spelling_hint AS spelling_hint,
       ha.i AS artic_i,
       a.name AS artic_name,
       l.text AS lyric_text
ORDER BY r.i, hp.i, ha.i
"""


# =============================================================================
# Reader Class
# =============================================================================

class GraphMusicReader:
    """
    Reads compositions from graph and reconstructs domain objects.
    
    Features:
    - Section caching with configurable TTL (default 5 minutes)
    - Type-safe row handling
    
    Args:
        host: Memgraph host address
        port: Memgraph port
        cache_ttl: Section cache TTL in seconds (default 300)
        cache_maxsize: Maximum cached sections (default 100)
    """
    
    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 7687,
        cache_ttl: int = 300,
        cache_maxsize: int = 100,
    ):
        self.db = Memgraph(host=host, port=port)
        self._section_cache: TTLCache[str, SectionSpec] = TTLCache(
            maxsize=cache_maxsize,
            ttl=cache_ttl,
        )
    
    def clear_cache(self) -> None:
        """Clear the section cache."""
        self._section_cache.clear()
    
    def load_composition_by_title(
        self,
        title: str,
    ) -> tuple[CompositionSpec, dict[str, SectionSpec]]:
        """
        Load a composition by title.
        
        Args:
            title: Composition title to search for
            
        Returns:
            Tuple of (CompositionSpec, sections_by_svid dict)
            
        Raises:
            ValueError: If composition not found
        """
        rows: list[CompositionRow] = list(
            self.db.execute_and_fetch(CQL_GET_COMPOSITION_BY_TITLE, {"title": title})
        )
        if not rows:
            raise ValueError(f"Composition not found: {title}")
        
        row = rows[0]
        return self._load_composition_version(row["cvid"], row["title"])
    
    def load_composition_by_cid(
        self,
        cid: str,
    ) -> tuple[CompositionSpec, dict[str, SectionSpec]]:
        """
        Load a composition by composition ID.
        
        Args:
            cid: Composition ID
            
        Returns:
            Tuple of (CompositionSpec, sections_by_svid dict)
            
        Raises:
            ValueError: If composition not found
        """
        rows: list[CompositionRow] = list(
            self.db.execute_and_fetch(CQL_GET_COMPOSITION_BY_CID, {"cid": cid})
        )
        if not rows:
            raise ValueError(f"Composition not found: {cid}")
        
        row = rows[0]
        return self._load_composition_version(row["cvid"], row["title"])
    
    def _load_composition_version(
        self,
        cvid: str,
        title: str,
    ) -> tuple[CompositionSpec, dict[str, SectionSpec]]:
        """Load full composition from version ID."""
        meter_map = self._load_meter_map(cvid)
        tempo_map = self._load_tempo_map(cvid)
        
        tracks = []
        sections_by_svid: dict[str, SectionSpec] = {}
        
        track_rows = list(self.db.execute_and_fetch(CQL_GET_TRACKS, {"cvid": cvid}))
        for tr in track_rows:
            track, track_sections = self._load_track(tr)
            tracks.append(track)
            sections_by_svid.update(track_sections)
        
        composition = CompositionSpec(
            title=title,
            meter_map=meter_map,
            tempo_map=tempo_map,
            tracks=tuple(tracks),
        )
        
        return composition, sections_by_svid
    
    def _load_meter_map(self, cvid: str) -> MeterMap:
        """Load MeterMap for a composition version."""
        rows: list[MeterMapChangeRow] = list(
            self.db.execute_and_fetch(CQL_GET_METER_MAP, {"cvid": cvid})
        )
        
        changes = []
        for row in rows:
            if row["at_bar"] is not None:
                changes.append(MeterChange(
                    at_bar=row["at_bar"],
                    ts=TimeSignature(num=row["ts_num"], den=row["ts_den"]),
                ))
        
        return MeterMap(changes=tuple(changes))
    
    def _load_tempo_map(self, cvid: str) -> TempoMap:
        """Load TempoMap for a composition version."""
        rows: list[TempoMapChangeRow] = list(
            self.db.execute_and_fetch(CQL_GET_TEMPO_MAP, {"cvid": cvid})
        )
        
        changes = []
        for row in rows:
            if row["at_bar"] is not None:
                changes.append(TempoChange(
                    at_bar=row["at_bar"],
                    at_beat=row["at_beat"],
                    tempo=TempoValue(
                        bpm=RationalTime(n=row["bpm_n"], d=row["bpm_d"]),
                        beat_unit_den=row["beat_unit_den"],
                    ),
                ))
        
        return TempoMap(changes=tuple(changes))
    
    def _load_track(
        self,
        track_row: TrackRow,
    ) -> tuple[TrackSpec, dict[str, SectionSpec]]:
        """Load a track and its referenced sections."""
        tvid: str = track_row["tvid"]
        
        config = TrackConfig(
            name=track_row["name"] or "Untitled",
            instrument_hint=track_row["instrument_hint"],
            midi_channel=track_row["midi_channel"],
            clef=track_row["clef"],
            transposition_semitones=track_row["transposition_semitones"] or 0,
        )
        
        placement_rows: list[PlacementRow] = list(
            self.db.execute_and_fetch(CQL_GET_TRACK_PLACEMENTS, {"tvid": tvid})
        )
        
        placements = []
        sections_by_svid: dict[str, SectionSpec] = {}
        
        for pr in placement_rows:
            svid = pr["svid"]
            
            if svid not in sections_by_svid:
                sections_by_svid[svid] = self._load_section(svid)
            
            placements.append(SectionPlacement(
                section_version_id=svid,
                start_bar=pr["start_bar"],
                repeats=pr["repeats"] or 1,
                transpose_semitones=pr["transpose_semitones"] or 0,
                role=pr["role"],
                gain_db=pr["gain_db"] or 0.0,
            ))
        
        track = TrackSpec(
            track_id=track_row["track_id"],
            config=config,
            placements=tuple(placements),
        )
        
        return track, sections_by_svid
    
    def _load_section(self, svid: str) -> SectionSpec:
        """
        Load a section by version ID.
        
        Uses caching to avoid repeated DB queries for the same section.
        """
        # Check cache first
        if svid in self._section_cache:
            return self._section_cache[svid]
        
        section_rows: list[SectionRow] = list(
            self.db.execute_and_fetch(CQL_GET_SECTION, {"svid": svid})
        )
        if not section_rows:
            raise ValueError(f"Section not found: {svid}")
        
        section_name = section_rows[0]["name"] or "Untitled"
        
        measure_rows: list[MeasureRow] = list(
            self.db.execute_and_fetch(CQL_GET_SECTION_MEASURES, {"svid": svid})
        )
        
        measures = []
        for mr in measure_rows:
            measure = self._load_measure(mr["mvid"], mr["local_ts_num"], mr["local_ts_den"])
            measures.append(measure)
        
        section = SectionSpec(name=section_name, measures=tuple(measures))
        
        # Cache for future requests
        self._section_cache[svid] = section
        return section
    
    def _load_measure(
        self,
        mvid: str,
        local_ts_num: Optional[int],
        local_ts_den: Optional[int],
    ) -> MeasureSpec:
        """Load a measure by version ID."""
        event_rows: list[EventRow] = list(
            self.db.execute_and_fetch(CQL_GET_MEASURE_EVENTS, {"mvid": mvid})
        )
        
        events_by_evid: dict[str, EventData] = {}
        
        for row in event_rows:
            evid = row["evid"]
            if evid not in events_by_evid:
                events_by_evid[evid] = {
                    "kind": row["kind"],
                    "offset_n": row["offset_n"],
                    "offset_d": row["offset_d"],
                    "dur_n": row["dur_n"],
                    "dur_d": row["dur_d"],
                    "velocity": row["velocity"],
                    "tie": row["tie"],
                    "meta_type": row["meta_type"],
                    "event_i": row["event_i"],
                    "pitches": [],
                    "articulations": [],
                    "lyric": row["lyric_text"],
                }
            
            if row["midi"] is not None:
                pitch_data = {
                    "i": row["pitch_i"],
                    "midi": row["midi"],
                    "cents_n": row["cents_n"],
                    "cents_d": row["cents_d"],
                    "spelling_hint": row["spelling_hint"],
                }
                if pitch_data not in events_by_evid[evid]["pitches"]:
                    events_by_evid[evid]["pitches"].append(pitch_data)
            
            if row["artic_name"] is not None:
                if row["artic_name"] not in events_by_evid[evid]["articulations"]:
                    events_by_evid[evid]["articulations"].append(row["artic_name"])
        
        events = []
        for evid, data in sorted(events_by_evid.items(), key=lambda x: x[1]["event_i"]):
            event = self._build_event(data)
            if event:
                events.append(event)
        
        local_ts = None
        if local_ts_num is not None and local_ts_den is not None:
            local_ts = TimeSignature(num=local_ts_num, den=local_ts_den)
        
        return MeasureSpec(
            local_time_signature=local_ts,
            events=tuple(events),
        )
    
    def _build_event(self, data: EventData) -> Optional[NoteEvent | RestEvent | ChordEvent | MetaEvent]:
        """Build a domain event from raw data."""
        kind = data["kind"]
        offset_q = RationalTime(n=data["offset_n"], d=data["offset_d"])
        dur_q = RationalTime(n=data["dur_n"], d=data["dur_d"])
        
        if kind == "note":
            pitches = sorted(data["pitches"], key=lambda p: p["i"] or 0)
            if not pitches:
                return None
            
            p = pitches[0]
            cents = None
            if p["cents_n"] is not None and p["cents_d"] is not None:
                cents = RationalTime(n=p["cents_n"], d=p["cents_d"])
            
            pitch = Pitch(
                midi=p["midi"],
                cents=cents,
                spelling_hint=p["spelling_hint"],
            )

            result = NoteEvent(
                offset_q=offset_q,
                dur_q=dur_q,
                pitch=pitch,
                velocity=data["velocity"],
                tie=data["tie"],
                articulations=tuple(data["articulations"]) if data["articulations"] else (),
                lyric=data["lyric"],
            )

            return result

        elif kind == "rest":
            return RestEvent(offset_q=offset_q, dur_q=dur_q)
        
        elif kind == "chord":
            pitches = sorted(data["pitches"], key=lambda p: p["i"] or 0)
            if not pitches:
                return None
            
            pitch_objs = []
            for p in pitches:
                cents = None
                if p["cents_n"] is not None and p["cents_d"] is not None:
                    cents = RationalTime(n=p["cents_n"], d=p["cents_d"])
                pitch_objs.append(Pitch(
                    midi=p["midi"],
                    cents=cents,
                    spelling_hint=p["spelling_hint"],
                ))
            
            return ChordEvent(
                offset_q=offset_q,
                dur_q=dur_q,
                pitches=tuple(pitch_objs),
                velocity=data["velocity"],
                tie=data["tie"],
                articulations=tuple(data["articulations"]) if data["articulations"] else (),
                lyric=data["lyric"],
            )
        
        elif kind == "meta":
            return MetaEvent(
                offset_q=offset_q,
                dur_q=dur_q,
                meta_type=data["meta_type"],
                payload={},
            )
        
        return None
