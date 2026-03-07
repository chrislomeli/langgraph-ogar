#!/usr/bin/env python3
"""
Demo: Load a composition from Memgraph and render to music21.

Prerequisites:
    - Run demo_twinkle_multipart.py first to populate the graph

Usage:
    python demo_render_from_graph.py                              # Show score
    python demo_render_from_graph.py --midi                       # Play MIDI
    python demo_render_from_graph.py --xml                        # Export MusicXML
    python demo_render_from_graph.py --title "Other Composition"  # Load different title
"""

import sys
sys.path.insert(0, "../src")

from symbolic_music.persistence import GraphMusicReader
from symbolic_music.rendering import render_composition


def parse_args(argv: list[str]) -> tuple[str, str]:
    title = "Twinkle Twinkle Little Harmony"
    output_mode = "show"
    
    i = 0
    while i < len(argv):
        arg = argv[i].lower()
        if arg == "--title" and i + 1 < len(argv):
            title = argv[i + 1]
            i += 2
        elif arg == "--midi":
            output_mode = "midi"
            i += 1
        elif arg == "--xml":
            output_mode = "xml"
            i += 1
        elif arg == "--text":
            output_mode = "text"
            i += 1
        else:
            i += 1
    
    return title, output_mode


def load_domain_from_graph(
    composition_title: str,
):
    """
    Memgraph -> Domain
    
    This corresponds to the "Graph -> Domain" section in docs/schema_mapping.md.
    
    Conceptually:
    - (Composition)-[:LATEST]->(CompositionVersion)
    - CompositionVersion -> MeterMapVersion / TempoMapVersion / TrackVersion
    - TrackVersion -[:USES_SECTION]-> SectionVersion
    - SectionVersion -> MeasureVersion -> EventVersion -> Pitch/Articulation/Lyric
    
    The reader returns:
    - composition: CompositionSpec (top-level domain object)
    - sections_by_svid: dict[str, SectionSpec] (content referenced by placements)
    """
    reader = GraphMusicReader()
    return reader.load_composition_by_title(composition_title)


def render_domain_to_music21(composition, sections_by_svid):
    """
    Domain -> music21
    
    This corresponds to the "Domain -> music21" mapping in docs/schema_mapping.md.
    
    Key ideas:
    - CompositionSpec -> stream.Score
    - TrackSpec -> stream.Part
    - SectionSpec is "unrolled" into Measures (no direct music21 equivalent)
    - MeasureSpec -> stream.Measure
    - Events -> Note/Rest/Chord/etc.
    """
    return render_composition(composition, sections_by_svid)


def print_score_summary(score) -> None:
    print(f"  Title: {score.metadata.title}")
    print(f"  Parts: {len(score.parts)}")
    for part in score.parts:
        measure_count = len(part.getElementsByClass("Measure"))
        print(f"    - {part.partName} ({measure_count} measures)")


def output_score(score, title: str, output_mode: str) -> None:
    if output_mode == "midi":
        print("\nPlaying MIDI...")
        score.show("midi")
    elif output_mode == "xml":
        filename = title.replace(" ", "_").lower() + ".musicxml"
        print(f"\nExporting to {filename}...")
        score.write("musicxml", fp=filename)
        print(f"Saved to {filename}")
    elif output_mode == "text":
        print("\nScore structure:")
        score.show("text")
    else:
        print("\nOpening score viewer...")
        score.show()


def main():
    title, output_mode = parse_args(sys.argv[1:])
    
    print(f"Loading '{title}' from graph...")
    
    try:
        composition, sections_by_svid = load_domain_from_graph(title)
    except ValueError as e:
        print(f"Error: {e}")
        print("\nMake sure you've run demo_twinkle_multipart.py first.")
        sys.exit(1)
    
    score = render_domain_to_music21(composition, sections_by_svid)
    print_score_summary(score)
    output_score(score, title=title, output_mode=output_mode)


if __name__ == "__main__":
    main()
