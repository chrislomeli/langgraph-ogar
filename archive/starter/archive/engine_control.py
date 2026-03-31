# from typing import Set, Dict, Optional
#
# from starter.model.base import WorkItem, Template
#
#
# def next_runnable_step(template: Template, item: WorkItem) -> Optional[str]:
#     """
#     Returns the next step_id whose dependencies are done and which is not done.
#     Simple topological selection. You can later add prioritization.
#     """
#     done: Set[str] = {sid for sid, inst in item.steps.items() if inst.status == "done"}
#
#     deps: Dict[str, Set[str]] = {s.step_id: set() for s in template.steps}
#     for e in template.edges:
#         deps[e.to].add(e.frm)
#
#     # Candidates: not done + all deps done
#     for s in template.steps:
#         sid = s.step_id
#         if sid in done:
#             continue
#         if deps[sid].issubset(done):
#             return sid
#     return None