from starter.model import WorkItem
from starter.engine import next_runnable_step, can_mark_done
from starter.templates import software_template


# ----------------------------
# Run the template DAG
# ----------------------------


item = WorkItem.instantiate_from_template(
    work_id="build_api",
    title="Build API",
    template=software_template,
)


def fill_payload(step: str, payload: dict) -> None:
    if step == "req":
        payload["what"] = "Build API"
        payload["why"] = "Expose planner service"
    elif step == "design":
        payload["approach"] = "FastAPI service with LangGraph planner"
    elif step == "build":
        payload["implementation_notes"] = "Create endpoints and graph control loop"
    elif step == "outcome":
        payload["acceptance_criteria"] = "API responds and tests pass"


while True:
    step = next_runnable_step(software_template, item)
    if step is None:
        print("\nAll steps complete.")
        break

    print(f"\nRunning step: {step}")

    fill_payload(step, item.steps[step].payload)
    can_mark_done(software_template, item, step)
    item.steps[step].status = "done"

# while True:
#     step = next_runnable_step(software_template, item)
#
#     if step is None:
#         print("\nAll steps complete.")
#         break
#
#     print(f"\nRunning step: {step}")
#     print("Next runnable:", next_runnable_step(software_template, item))
#
#     payload = item.steps[step].payload
#
#     if step == "req":
#         payload["what"] = "Build API"
#         payload["why"] = "Expose engine engine"
#
#     elif step == "design":
#         payload["approach"] = "FastAPI engine with LangGraph engine"
#
#     elif step == "build":
#         payload["implementation_notes"] = "Create endpoints and graph control loop"
#
#     elif step == "outcome":
#         payload["acceptance_criteria"] = "API responds and tests pass"
#
#     can_mark_done(software_template, item, step)
#
#     item.steps[step].status = "done"
#     print("Payload:", payload)