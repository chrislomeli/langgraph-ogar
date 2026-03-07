#!/usr/bin/env python3
"""
Demo: Full pipeline — Sketch → Plan → Compile → Render.

Exercises the complete intent layer without requiring Memgraph.
Shows:
1. User sketch (free-text prompt + hints)
2. Deterministic engine producing a PlanBundle
3. Pattern compiler producing domain IR (CompositionSpec + SectionSpecs)
4. music21 rendering to Score
5. Plan-level refinement ("add a bridge") → recompile → re-render

Usage:
    python demo_sketch_to_score.py                # Show score summary
    python demo_sketch_to_score.py --text          # Show score structure
    python demo_sketch_to_score.py --midi          # Play MIDI
    python demo_sketch_to_score.py --xml           # Export MusicXML
"""

import sys
sys.path.insert(0, "../src")

from intent.sketch_models import Sketch, VoiceHint
from intent.planner import DeterministicPlanner
from intent.compiler import PatternCompiler
from symbolic_music.rendering import render_composition


# ============================================================================
# Helpers
# ============================================================================

def print_plan_summary(plan):
    """Print a human-readable summary of the PlanBundle."""
    print(f"\n{'='*60}")
    print(f"  PLAN: {plan.title}")
    print(f"{'='*60}")
    print(f"  Key: {plan.key}  |  Tempo: {plan.tempo_bpm} BPM  |  Time: {plan.time_signature}")
    print(f"  Bundle ID: {plan.bundle_id}")

    print(f"\n  Voices ({len(plan.voice_plan.voices)}):")
    for v in plan.voice_plan.voices:
        print(f"    - {v.name:20s}  role={v.role.value:15s}  inst={v.instrument}")

    print(f"\n  Form ({plan.form_plan.total_bars()} bars):")
    for tp in plan.form_plan.timeline:
        sp = plan.form_plan.get_section(tp.section_id)
        if sp:
            print(f"    bar {tp.start_bar:3d}: {sp.section_id:12s}  ({sp.role.value}, {sp.bars} bars, energy={sp.energy.value})")

    print(f"\n  Harmony:")
    for hs in plan.harmony_plan.sections:
        chords_str = " | ".join(ch.symbol for ch in hs.chords[:8])
        if len(hs.chords) > 8:
            chords_str += " ..."
        print(f"    {hs.section_id:12s}: {chords_str}")

    print(f"\n  Groove:")
    for gs in plan.groove_plan.sections:
        print(f"    {gs.section_id:12s}: feel={gs.feel.value}, drums={gs.drum_density.value}, bass={gs.bass_approach}")


def print_compile_summary(result):
    """Print a summary of the compiled IR."""
    comp = result.composition
    print(f"\n{'='*60}")
    print(f"  COMPILED: {comp.title}")
    print(f"{'='*60}")
    print(f"  Tracks: {len(comp.tracks)}")
    print(f"  Sections generated: {len(result.sections)}")

    for track in comp.tracks:
        total_measures = 0
        for pl in track.placements:
            sec = result.sections.get(pl.section_version_id)
            if sec:
                total_measures += len(sec.measures) * pl.repeats
        print(f"    - {track.config.name:20s}  placements={len(track.placements)}, measures={total_measures}")

    if result.warnings:
        print(f"\n  Warnings:")
        for w in result.warnings:
            print(f"    ! {w}")


def print_score_summary(score):
    """Print a summary of the rendered music21 Score."""
    print(f"\n{'='*60}")
    print(f"  SCORE: {score.metadata.title}")
    print(f"{'='*60}")
    print(f"  Parts: {len(score.parts)}")
    for part in score.parts:
        measure_count = len(part.getElementsByClass("Measure"))
        note_count = len(part.flatten().notes)
        print(f"    - {part.partName:20s}  measures={measure_count}, notes={note_count}")


def output_score(score, title, mode):
    """Output the score in the requested format."""
    if mode == "midi":
        print("\nPlaying MIDI...")
        score.show("midi")
    elif mode == "xml":
        filename = title.replace(" ", "_").lower() + ".musicxml"
        print(f"\nExporting to {filename}...")
        score.write("musicxml", fp=filename)
        print(f"Saved to {filename}")
    elif mode == "text":
        print("\nScore structure:")
        score.show("text")
    else:
        print("\n(Use --text, --midi, or --xml to output the score)")


def parse_args(argv):
    mode = "summary"
    for arg in argv:
        if arg == "--midi":
            mode = "midi"
        elif arg == "--xml":
            mode = "xml"
        elif arg == "--text":
            mode = "text"
        elif arg == "--show":
            mode = "show"
    return mode


# ============================================================================
# Main demo
# ============================================================================

def main():
    output_mode = parse_args(sys.argv[1:])

    planner = DeterministicPlanner()
    compiler = PatternCompiler()

    # ------------------------------------------------------------------
    # Step 1: User sketch
    # ------------------------------------------------------------------
    print("\n" + "="*60)
    print("  STEP 1: User Sketch")
    print("="*60)

    sketch = Sketch(
        prompt="Rock tune with a bossa-nova groove, A minor, verse-chorus-verse, around 120 bpm",
        title="Bossa Rock Demo",
        voice_hints=[
            VoiceHint(name="piano", importance="required", notes="comping, not too busy"),
            VoiceHint(name="bass", importance="required"),
            VoiceHint(name="drums", importance="required"),
        ],
        avoid=["synths", "strings"],
    )

    print(f"  Prompt: \"{sketch.prompt}\"")
    print(f"  Title:  {sketch.title}")
    print(f"  Voices: {', '.join(v.name for v in sketch.voice_hints)}")
    print(f"  Avoid:  {', '.join(sketch.avoid)}")

    # ------------------------------------------------------------------
    # Step 2: Plan
    # ------------------------------------------------------------------
    print("\n" + "="*60)
    print("  STEP 2: Planner → PlanBundle")
    print("="*60)

    plan = planner.plan(sketch)
    print_plan_summary(plan)

    # ------------------------------------------------------------------
    # Step 3: Compile
    # ------------------------------------------------------------------
    print("\n" + "="*60)
    print("  STEP 3: Compiler → Composition IR")
    print("="*60)

    result = compiler.compile(plan)
    print_compile_summary(result)

    # ------------------------------------------------------------------
    # Step 4: Render
    # ------------------------------------------------------------------
    print("\n" + "="*60)
    print("  STEP 4: Render → music21 Score")
    print("="*60)

    score = render_composition(result.composition, result.sections)
    print_score_summary(score)
    output_score(score, plan.title, output_mode)

    # ------------------------------------------------------------------
    # Step 5: Refinement — "Add a bridge"
    # ------------------------------------------------------------------
    print("\n" + "="*60)
    print("  STEP 5: Refinement — \"Add a bridge after the second chorus\"")
    print("="*60)

    refined_plan = planner.refine(plan, "Add a bridge after the second chorus")
    print_plan_summary(refined_plan)

    # Recompile with refined plan
    refined_result = compiler.compile(refined_plan)
    print_compile_summary(refined_result)

    # Re-render
    refined_score = render_composition(refined_result.composition, refined_result.sections)
    print_score_summary(refined_score)

    # ------------------------------------------------------------------
    # Step 6: Scoped regeneration — "Regenerate only drums"
    # ------------------------------------------------------------------
    print("\n" + "="*60)
    print("  STEP 6: Scoped Regeneration — drums only")
    print("="*60)

    from intent.compiler_interface import CompileOptions

    # Find the drums voice_id
    drums_vid = None
    for v in refined_plan.voice_plan.voices:
        if v.role.value == "drums":
            drums_vid = v.voice_id
            break

    if drums_vid:
        scoped_opts = CompileOptions(
            regenerate_voices={drums_vid},
            seed=99,  # different seed for variety
        )
        scoped_result = compiler.compile(refined_plan, options=scoped_opts, previous=refined_result)
        print_compile_summary(scoped_result)
        print(f"\n  Only drums were regenerated. Other voices preserved from previous result.")
    else:
        print("  (No drums voice found)")

    # ------------------------------------------------------------------
    # Summary
    # ------------------------------------------------------------------
    print("\n" + "="*60)
    print("  PIPELINE COMPLETE")
    print("="*60)
    print(f"  Original:  {plan.form_plan.total_bars()} bars, {len(plan.voice_plan.voices)} voices")
    print(f"  Refined:   {refined_plan.form_plan.total_bars()} bars (bridge added)")
    print(f"  Sections:  {len(refined_result.sections)} generated")
    print(f"  Lineage:   Sketch → PlanBundle({plan.bundle_id}) → PlanBundle({refined_plan.bundle_id}) → CompositionSpec")
    print()


if __name__ == "__main__":
    main()
