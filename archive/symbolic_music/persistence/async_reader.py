"""
Async graph database read operations.

Async version of reader.py using neo4j AsyncGraphDatabase.
Use this for API/web engine contexts where non-blocking IO is important.
"""

from typing import Optional, TypeVar

T = TypeVar("T")

from cachetools import TTLCache
from neo4j import AsyncGraphDatabase

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
from symbolic_music.persistence.types import (
    CompositionRow,
    EventData,
    EventRow,
    MeasureRow,
    MeterMapChangeRow,
    PlacementRow,
    SectionRow,
    TempoMapChangeRow,
    TrackRow,
)


# =============================================================================
# Cypher Queries (same as sync version)
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
# Async Reader Class
# =============================================================================

class AsyncGraphMusicReader:
    """
    Async version of GraphMusicReader.
    
    Uses neo4j AsyncGraphDatabase for non-blocking database operations.
    Ideal for FastAPI, aiohttp, or other async web frameworks.
    
    Args:
        uri: Bolt URI (e.g., "bolt://localhost:7687")
        cache_ttl: Section cache TTL in seconds (default 300)
        cache_maxsize: Maximum cached sections (default 100)
    
    Usage:
        async with AsyncGraphMusicReader() as reader:
            comp, sections = await reader.load_composition_by_title("My Song")
    """
    
    def __init__(
        self,
        uri: str = "bolt://localhost:7687",
        cache_ttl: int = 300,
        cache_maxsize: int = 100,
    ):
        self._uri = uri
        self._driver = AsyncGraphDatabase.driver(uri)
        self._section_cache: TTLCache[str, SectionSpec] = TTLCache(
            maxsize=cache_maxsize,
            ttl=cache_ttl,
        )
    
    async def __aenter__(self) -> "AsyncGraphMusicReader":
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self.close()
    
    async def close(self) -> None:
        """Close the database connection."""
        await self._driver.close()
    
    def clear_cache(self) -> None:
        """Clear the section cache."""
        self._section_cache.clear()
    
    async def _execute(self, query: str, params: dict, row_type: type[T] = dict) -> list[T]:
        """
        Execute a query and return results as list of typed dicts.
        
        The row_type parameter is used for type inference only - no runtime validation.
        """
        async with self._driver.session() as session:
            result = await session.run(query, params)
            return [record.data() async for record in result]  # type: ignore[return-value]
    
    async def load_composition_by_title(
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
        rows = await self._execute(
            CQL_GET_COMPOSITION_BY_TITLE, {"title": title}, CompositionRow
        )
        if not rows:
            raise ValueError(f"Composition not found: {title}")
        
        row = rows[0]
        return await self._load_composition_version(row["cvid"], row["title"])
    
    async def load_composition_by_cid(
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
        rows = await self._execute(
            CQL_GET_COMPOSITION_BY_CID, {"cid": cid}, CompositionRow
        )
        if not rows:
            raise ValueError(f"Composition not found: {cid}")
        
        row = rows[0]
        return await self._load_composition_version(row["cvid"], row["title"])
    
    async def _load_composition_version(
        self,
        cvid: str,
        title: str,
    ) -> tuple[CompositionSpec, dict[str, SectionSpec]]:
        """Load full composition from version ID."""
        meter_map = await self._load_meter_map(cvid)
        tempo_map = await self._load_tempo_map(cvid)
        
        tracks = []
        sections_by_svid: dict[str, SectionSpec] = {}
        
        track_rows = await self._execute(
            CQL_GET_TRACKS, {"cvid": cvid}, TrackRow
        )
        for tr in track_rows:
            track, track_sections = await self._load_track(tr)
            tracks.append(track)
            sections_by_svid.update(track_sections)
        
        composition = CompositionSpec(
            title=title,
            meter_map=meter_map,
            tempo_map=tempo_map,
            tracks=tuple(tracks),
        )
        
        return composition, sections_by_svid
    
    async def _load_meter_map(self, cvid: str) -> MeterMap:
        """Load MeterMap for a composition version."""
        rows = await self._execute(
            CQL_GET_METER_MAP, {"cvid": cvid}, MeterMapChangeRow
        )
        
        changes = []
        for row in rows:
            if row["at_bar"] is not None:
                changes.append(MeterChange(
                    at_bar=row["at_bar"],
                    ts=TimeSignature(num=row["ts_num"], den=row["ts_den"]),
                ))
        
        return MeterMap(changes=tuple(changes))
    
    async def _load_tempo_map(self, cvid: str) -> TempoMap:
        """Load TempoMap for a composition version."""
        rows = await self._execute(
            CQL_GET_TEMPO_MAP, {"cvid": cvid}, TempoMapChangeRow
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
    
    async def _load_track(
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
        
        placement_rows = await self._execute(
            CQL_GET_TRACK_PLACEMENTS, {"tvid": tvid}, PlacementRow
        )
        
        placements = []
        sections_by_svid: dict[str, SectionSpec] = {}
        
        for pr in placement_rows:
            svid = pr["svid"]
            
            if svid not in sections_by_svid:
                sections_by_svid[svid] = await self._load_section(svid)
            
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
    
    async def _load_section(self, svid: str) -> SectionSpec:
        """
        Load a section by version ID.
        
        Uses caching to avoid repeated DB queries for the same section.
        """
        # Check cache first
        if svid in self._section_cache:
            return self._section_cache[svid]
        
        section_rows = await self._execute(
            CQL_GET_SECTION, {"svid": svid}, SectionRow
        )
        if not section_rows:
            raise ValueError(f"Section not found: {svid}")
        
        section_name = section_rows[0]["name"] or "Untitled"
        
        measure_rows = await self._execute(
            CQL_GET_SECTION_MEASURES, {"svid": svid}, MeasureRow
        )
        
        measures = []
        for mr in measure_rows:
            measure = await self._load_measure(
                mr["mvid"], mr["local_ts_num"], mr["local_ts_den"]
            )
            measures.append(measure)
        
        section = SectionSpec(name=section_name, measures=tuple(measures))
        
        # Cache for future requests
        self._section_cache[svid] = section
        return section
    
    async def _load_measure(
        self,
        mvid: str,
        local_ts_num: Optional[int],
        local_ts_den: Optional[int],
    ) -> MeasureSpec:
        """Load a measure by version ID."""
        event_rows = await self._execute(
            CQL_GET_MEASURE_EVENTS, {"mvid": mvid}, EventRow
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
    
    def _build_event(
        self, data: EventData
    ) -> Optional[NoteEvent | RestEvent | ChordEvent | MetaEvent]:
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

            return NoteEvent(
                offset_q=offset_q,
                dur_q=dur_q,
                pitch=pitch,
                velocity=data["velocity"],
                tie=data["tie"],
                articulations=tuple(data["articulations"]) if data["articulations"] else (),
                lyric=data["lyric"],
            )

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
