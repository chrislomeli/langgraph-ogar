# Archive

Code moved here during cleanup. Not dead — contains ideas worth revisiting.

## What's here

| File | Origin | Why it's interesting |
|---|---|---|
| `init_project.py` | `scripts/` | Manual project creation — reference for what `call_the_ai` goals stub produces |
| `requirements_session.py` | `scripts/` | Manual requirements + uncertainty creation — shows uncertainty-on-ambiguity pattern |
| `consult_goals.py` | `consult/` | `ConsultingOutcome` dataclass with `(project, questions, blockers, notes)` — richer than current `ProjectPatch` |
| `consult_requirements.py` | `consult/` | Precondition checks + consulting logic spelled out explicitly |
| `engine_control.py` | `engine/` | Commented-out duplicate of schedule.py |
| `engine_schedule.py` | `engine/` | DAG-based step scheduling for WorkItems (future "execution" stage) |
| `engine_validate.py` | `engine/` | Required-field validation for template steps |
| `model_base.py` | `model/` | Template/WorkItem/StepInstance models with DAG cycle detection |
| `nodes_m3_tutorial/` | `graph/goals/nodes/` | Old M3 LangGraph tutorial nodes (music plans, interrupt-based review) |

## Future extensions these suggest

1. **Uncertainty creation during consult** — `requirements_session.py` adds uncertainties when requirements raise ambiguities
2. **Richer consulting outcome** — `consult_goals.py` distinguishes questions vs blockers vs notes
3. **Execution stage** — `model_base.py` + `engine_schedule.py` + `engine_validate.py` form a work-item execution layer
4. **Post-run reports** — `engine/reports.py` (still active) can surface stale/orphan/blocking uncertainties
