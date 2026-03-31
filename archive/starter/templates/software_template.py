from starter.model import Template, TemplateStep, TemplateEdge

software_template = Template(
    template_id="tmpl_software_v1",
    name="Software delivery v1",
    steps=[
        TemplateStep(step_id="req", kind="artifact", title="Requirements (what/why)", phase="requirements", required_fields=["what", "why"]),
        TemplateStep(step_id="design", kind="artifact", title="Design (how)", phase="design", required_fields=["approach"]),
        TemplateStep(step_id="build", kind="artifact", title="Build", phase="build", required_fields=["implementation_notes"]),
        TemplateStep(step_id="outcome", kind="check", title="Outcome / acceptance", phase="outcome", required_fields=["acceptance_criteria"]),
    ],
    edges=[
        TemplateEdge(frm="req", to="design"),
        TemplateEdge(frm="design", to="build"),
        TemplateEdge(frm="build", to="outcome"),
    ],
)