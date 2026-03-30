"""
Example data from WHITEBOARD_ONTOLOGY.md converted to Pydantic models.

This demonstrates how to instantiate the models with real data from the design document.
"""
from conversation_engine.models import (
    Feature,
    Goal,
    GuidingPrinciple,
    Requirement,
    Capability,
    UseCase,
    Scenario,
    DesignArtifact,
    Decision,
    Constraint,
    Component,
    Dependency,
    DocumentationArtifact,
    GoalRequirementTrace,
    RequirementCapabilityTrace,
    CapabilityComponentTrace,
    ComponentDependencyTrace,
    IntegrityRule,
    GraphQueryPattern,
    EdgeCheck,
    PathStep,
)


def get_feature() -> Feature:
    """The main feature definition."""
    return Feature(
        id="feature-reusable-conversation-engine",
        name="Reusable Conversation Engine",
        description="A conversation-driven feature that helps a user explore, critique, and optionally synthesize structured planning artifacts."
    )


def get_goals() -> list[Goal]:
    """Goals from the Intent Layer."""
    return [
        Goal(
            id="goal-structured-convergence",
            name="Structured Convergence",
            statement="Enable the system to transform ambiguous human input into progressively structured planning artifacts."
        ),
        Goal(
            id="goal-reusable-artifact-synthesis",
            name="Reusable Artifact Synthesis",
            statement="Enable a common conversation-driven process to produce multiple kinds of structured planning artifacts from ambiguous human input."
        ),
        Goal(
            id="goal-traceable-synthesis",
            name="Traceable Synthesis",
            statement="Ensure intermediate synthesis artifacts remain inspectable and traceable."
        ),
        Goal(
            id="goal-human-governance",
            name="Controlled Human Governance",
            statement="Allow humans to intervene at meaningful decision points."
        ),
        Goal(
            id="goal-artifact-integrity",
            name="Artifact Integrity",
            statement="Ensure artifacts comply with explicit domain validation rules."
        ),
    ]


def get_guiding_principles() -> list[GuidingPrinciple]:
    """Guiding principles from the Intent Layer."""
    return [
        GuidingPrinciple(
            id="gp-001",
            name="Exploration without formalization",
            statement="Conversation should support exploration without forcing formalization."
        ),
        GuidingPrinciple(
            id="gp-002",
            name="Explicit artifact creation",
            statement="Artifacts are created only by explicit user request."
        ),
        GuidingPrinciple(
            id="gp-003",
            name="Critique over compliance",
            statement="The system should critique ideas rather than merely comply."
        ),
        GuidingPrinciple(
            id="gp-004",
            name="Inspectable intermediates",
            statement="Intermediate artifacts must remain inspectable."
        ),
    ]


def get_requirements() -> list[Requirement]:
    """Requirements from the Requirement Layer."""
    return [
        Requirement(id="REQ-001", name="Advisory Conversation Support"),
        Requirement(id="REQ-002", name="Explicit Synthesis Trigger"),
        Requirement(id="REQ-003", name="Critical Interaction"),
        Requirement(id="REQ-004", name="Clarification Detection"),
        Requirement(id="REQ-005", name="Artifact Draft Generation"),
        Requirement(id="REQ-006", name="Reusable Artifact Synthesis"),
        Requirement(id="REQ-007", name="Iterative Refinement"),
        Requirement(id="REQ-008", name="Context Utilization"),
        Requirement(id="REQ-009", name="Structured Intermediate Artifacts"),
        Requirement(id="REQ-010", name="Persistent Working State"),
        Requirement(id="REQ-011", name="Artifact Versioning"),
        Requirement(id="REQ-012", name="Audit Trail"),
        Requirement(id="REQ-013", name="Human Approval Workflow"),
        Requirement(id="REQ-014", name="Policy Auto Approval"),
        Requirement(id="REQ-015", name="Decision Capture"),
        Requirement(id="REQ-016", name="Deterministic Validation"),
        Requirement(id="REQ-017", name="Actionable Validation Feedback"),
        Requirement(id="REQ-018", name="Domain Rule Enforcement"),
        Requirement(id="REQ-019", name="Artifact-Type Configuration"),
        Requirement(id="REQ-020", name="Single User Operation"),
    ]


def get_capabilities() -> list[Capability]:
    """Capabilities from the Behavior Layer."""
    return [
        Capability(id="cap-conversation-workspace", name="Conversation Workspace"),
        Capability(id="cap-artifact-synthesis", name="Artifact Synthesis"),
        Capability(id="cap-critique-and-clarification", name="Critique and Clarification"),
        Capability(id="cap-governance-and-approval", name="Governance and Approval"),
        Capability(id="cap-validation-and-integrity", name="Validation and Integrity"),
        Capability(id="cap-state-versioning-audit", name="State Versioning and Audit"),
        Capability(id="cap-artifact-type-configuration", name="Artifact Type Configuration"),
    ]


def get_use_cases() -> list[UseCase]:
    """Use cases from the Behavior Layer."""
    return [
        UseCase(id="uc-explore-without-formalizing", name="Explore ideas"),
        UseCase(id="uc-synthesize-artifact-from-conversation", name="Synthesize artifact"),
        UseCase(id="uc-critique-existing-artifact", name="Critique artifact"),
        UseCase(id="uc-revise-artifact-through-iteration", name="Iteratively revise artifact"),
        UseCase(id="uc-approve-or-promote-artifact", name="Approve artifact"),
        UseCase(id="uc-resume-synthesis-session", name="Resume synthesis"),
    ]


def get_scenarios() -> list[Scenario]:
    """Scenarios from the Behavior Layer."""
    return [
        Scenario(id="sc-explore-no-generation", name="Whiteboard discussion"),
        Scenario(id="sc-explicit-goal-generation", name="Generate goals"),
        Scenario(id="sc-critique-only", name="Critique artifact"),
        Scenario(id="sc-revise-after-critique", name="Revise artifact"),
        Scenario(id="sc-human-approval", name="Human approval"),
        Scenario(id="sc-policy-auto-approval", name="Policy approval"),
        Scenario(id="sc-resume-from-sidecar-state", name="Resume from state"),
    ]


def get_design_artifacts() -> list[DesignArtifact]:
    """Design artifacts from the Design Knowledge Layer."""
    return [
        DesignArtifact(
            id="design-artifact-synthesis-pipeline",
            name="Artifact Synthesis Pipeline",
            statement="Defines the reusable synthesis pipeline."
        ),
        DesignArtifact(
            id="design-conversation-workspace-model",
            name="Conversation Workspace Model",
            statement="Defines working conversational state."
        ),
        DesignArtifact(
            id="design-artifact-type-configuration-model",
            name="Artifact Type Configuration Model",
            statement="Defines artifact specific configuration."
        ),
    ]


def get_decisions() -> list[Decision]:
    """Decisions from the Design Knowledge Layer."""
    return [
        Decision(
            id="decision-explicit-synthesis-only",
            name="Explicit synthesis only",
            statement="Artifacts generated only on explicit request."
        ),
        Decision(
            id="decision-llm-not-source-of-integrity",
            name="LLM not source of integrity",
            statement="Validation must be deterministic outside the LLM."
        ),
        Decision(
            id="decision-single-user-initial-scope",
            name="Single user initial scope",
            statement="Initial version supports single-user workflow."
        ),
    ]


def get_constraints() -> list[Constraint]:
    """Constraints from the Design Knowledge Layer."""
    return [
        Constraint(
            id="constraint-external-state-sidecar",
            name="External state sidecar",
            statement="State stored in external service."
        ),
        Constraint(
            id="constraint-intermediate-artifacts-inspectable",
            name="Intermediate artifacts inspectable",
            statement="Intermediate artifacts must be inspectable."
        ),
    ]


def get_components() -> list[Component]:
    """Components from the Design Layer."""
    return [
        Component(id="component-conversation-orchestrator", name="Conversation Orchestrator"),
        Component(id="component-artifact-synthesizer", name="Artifact Synthesizer"),
        Component(id="component-critic", name="Artifact Critic"),
        Component(id="component-validator", name="Artifact Validator"),
        Component(id="component-governance-engine", name="Governance Engine"),
        Component(id="component-state-manager", name="State Manager"),
        Component(id="component-artifact-type-registry", name="Artifact Type Registry"),
    ]


def get_dependencies() -> list[Dependency]:
    """Dependencies from the Design Layer."""
    return [
        Dependency(id="dependency-llm-runtime", name="LLM Runtime"),
        Dependency(id="dependency-state-sidecar-service", name="State Service"),
        Dependency(id="dependency-validation-rule-library", name="Validation Rule Library"),
    ]


def get_documentation_artifacts() -> list[DocumentationArtifact]:
    """Documentation artifacts from the Design Knowledge Layer."""
    return [
        DocumentationArtifact(id="doc-feature-overview", name="Feature Overview"),
        DocumentationArtifact(id="doc-artifact-synthesis-guide", name="Artifact Synthesis Guide"),
        DocumentationArtifact(id="doc-governance-and-validation-guide", name="Governance Guide"),
    ]


def get_goal_requirement_traces() -> list[GoalRequirementTrace]:
    """Traceability from goals to requirements."""
    return [
        GoalRequirementTrace(
            goal_id="goal-structured-convergence",
            requirement_ids=["REQ-001", "REQ-004", "REQ-005", "REQ-007"]
        ),
        GoalRequirementTrace(
            goal_id="goal-reusable-artifact-synthesis",
            requirement_ids=["REQ-005", "REQ-006", "REQ-019"]
        ),
        GoalRequirementTrace(
            goal_id="goal-traceable-synthesis",
            requirement_ids=["REQ-009", "REQ-010", "REQ-011", "REQ-012"]
        ),
        GoalRequirementTrace(
            goal_id="goal-human-governance",
            requirement_ids=["REQ-002", "REQ-013", "REQ-014", "REQ-015"]
        ),
        GoalRequirementTrace(
            goal_id="goal-artifact-integrity",
            requirement_ids=["REQ-016", "REQ-017", "REQ-018"]
        ),
    ]


def get_requirement_capability_traces() -> list[RequirementCapabilityTrace]:
    """Traceability from requirements to capabilities (sample)."""
    return [
        RequirementCapabilityTrace(
            requirement_id="REQ-001",
            capability_ids=["cap-conversation-workspace"]
        ),
        RequirementCapabilityTrace(
            requirement_id="REQ-002",
            capability_ids=["cap-governance-and-approval"]
        ),
        RequirementCapabilityTrace(
            requirement_id="REQ-005",
            capability_ids=["cap-artifact-synthesis"]
        ),
        RequirementCapabilityTrace(
            requirement_id="REQ-016",
            capability_ids=["cap-validation-and-integrity"]
        ),
    ]


def get_capability_component_traces() -> list[CapabilityComponentTrace]:
    """Traceability from capabilities to components."""
    return [
        CapabilityComponentTrace(
            capability_id="cap-conversation-workspace",
            component_ids=["component-conversation-orchestrator", "component-state-manager"]
        ),
        CapabilityComponentTrace(
            capability_id="cap-artifact-synthesis",
            component_ids=["component-artifact-synthesizer"]
        ),
        CapabilityComponentTrace(
            capability_id="cap-critique-and-clarification",
            component_ids=["component-critic"]
        ),
        CapabilityComponentTrace(
            capability_id="cap-governance-and-approval",
            component_ids=["component-governance-engine"]
        ),
        CapabilityComponentTrace(
            capability_id="cap-validation-and-integrity",
            component_ids=["component-validator"]
        ),
        CapabilityComponentTrace(
            capability_id="cap-state-versioning-audit",
            component_ids=["component-state-manager"]
        ),
        CapabilityComponentTrace(
            capability_id="cap-artifact-type-configuration",
            component_ids=["component-artifact-type-registry"]
        ),
    ]


def get_component_dependency_traces() -> list[ComponentDependencyTrace]:
    """Traceability from components to dependencies."""
    return [
        ComponentDependencyTrace(
            component_id="component-artifact-synthesizer",
            dependency_ids=["dependency-llm-runtime"]
        ),
        ComponentDependencyTrace(
            component_id="component-critic",
            dependency_ids=["dependency-llm-runtime"]
        ),
        ComponentDependencyTrace(
            component_id="component-state-manager",
            dependency_ids=["dependency-state-sidecar-service"]
        ),
        ComponentDependencyTrace(
            component_id="component-validator",
            dependency_ids=["dependency-validation-rule-library"]
        ),
    ]


def get_sample_integrity_rules() -> list[IntegrityRule]:
    """Sample integrity rules from the ontology."""
    return [
        IntegrityRule(
            id="rule-goal-must-have-requirement",
            name="Goal must map to requirement",
            description="Every goal must map to at least one requirement.",
            applies_to_node_type="goal",
            rule_type="minimum_outgoing_edge_count",
            edge_type="SATISFIED_BY",
            target_node_types=["requirement"],
            minimum_count=1,
            severity="high",
            failure_message_template="Goal '{subject_name}' has no linked requirements."
        ),
        IntegrityRule(
            id="rule-requirement-must-have-capability",
            name="Requirement must map to capability",
            description="Every requirement must map to at least one capability.",
            applies_to_node_type="requirement",
            rule_type="minimum_outgoing_edge_count",
            edge_type="REALIZED_BY",
            target_node_types=["capability"],
            minimum_count=1,
            severity="high",
            failure_message_template="Requirement '{subject_name}' has no linked capabilities."
        ),
        IntegrityRule(
            id="rule-capability-must-have-component",
            name="Capability must map to component",
            description="Every capability must map to at least one component.",
            applies_to_node_type="capability",
            rule_type="minimum_outgoing_edge_count",
            edge_type="REALIZED_BY",
            target_node_types=["component"],
            minimum_count=1,
            severity="high",
            failure_message_template="Capability '{subject_name}' has no linked components."
        ),
    ]


def get_sample_query_patterns() -> list[GraphQueryPattern]:
    """Sample query patterns from the ontology."""
    return [
        GraphQueryPattern(
            id="query-missing-goal-coverage",
            name="Missing Goal Coverage",
            description="Find goals that are not linked to any requirements.",
            subject_node_type="goal",
            query_intent="gap_detection",
            checks=[
                EdgeCheck(
                    edge_type="SATISFIED_BY",
                    target_node_types=["requirement"],
                    expected_min_count=1
                )
            ],
            output_kind="finding_set"
        ),
        GraphQueryPattern(
            id="query-missing-requirement-realization",
            name="Missing Requirement Realization",
            description="Find requirements that are not linked to any capabilities.",
            subject_node_type="requirement",
            query_intent="gap_detection",
            checks=[
                EdgeCheck(
                    edge_type="REALIZED_BY",
                    target_node_types=["capability"],
                    expected_min_count=1
                )
            ],
            output_kind="finding_set"
        ),
        GraphQueryPattern(
            id="query-goal-to-component-lineage",
            name="Goal to Component Lineage",
            description="Show the traceability chain from a goal down to realizing components.",
            subject_node_type="goal",
            query_intent="lineage_trace",
            path_pattern=[
                PathStep(edge_type="SATISFIED_BY", target_node_types=["requirement"]),
                PathStep(edge_type="REALIZED_BY", target_node_types=["capability"]),
                PathStep(edge_type="REALIZED_BY", target_node_types=["component"]),
            ],
            output_kind="trace_report"
        ),
    ]
