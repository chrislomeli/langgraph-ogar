from starter.model import Template, TemplateStep, TemplateEdge

research_template = Template(
    template_id="tmpl_research_v1",
    name="Research exploration v1",
    steps=[
        TemplateStep(step_id="question", kind="artifact", title="Research question", required_fields=["question"]),
        TemplateStep(step_id="sources", kind="artifact", title="Collect sources", required_fields=["sources"]),
        TemplateStep(step_id="notes", kind="artifact", title="Synthesize notes", required_fields=["summary", "claims"]),
        TemplateStep(step_id="next", kind="decision", title="Decide next actions", required_fields=["decision", "rationale"]),
    ],
    edges=[
        TemplateEdge(frm="question", to="sources"),
        TemplateEdge(frm="sources", to="notes"),
        TemplateEdge(frm="notes", to="next"),
    ],
)