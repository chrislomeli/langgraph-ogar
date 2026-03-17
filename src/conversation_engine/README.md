# Conversation Engine - Pydantic Models

This package implements the domain models for the **Reusable Conversation Engine** as defined in `design/WHITEBOARD_ONTOLOGY.md`.

## Overview

The Conversation Engine is designed to enable structured planning conversations between humans and AI, transforming ambiguous input into structured planning artifacts through conversation, critique, and governance.

## Design Philosophy

These models follow strong design principles:

- **Strongly typed**: All inputs/outputs use Pydantic models with explicit types
- **Immutable where appropriate**: Rules and edges are frozen; nodes are mutable
- **Clear separation of concerns**: Models organized by layer (nodes, edges, rules, queries, assessments)
- **Graph-native**: Designed for knowledge graph representation with explicit node and edge types
- **AI-first**: Built to support AI reasoning over architectural knowledge

## Model Structure

### Base Models (`models/base.py`)

- **`NodeType`**: Literal type defining all valid node types
- **`EdgeType`**: Literal type defining all valid edge types
- **`BaseNode`**: Base class for all knowledge graph nodes
- **`BaseEdge`**: Base class for all knowledge graph edges

### Node Models (`models/nodes.py`)

Knowledge graph nodes representing architectural artifacts:

- **`Feature`**: High-level system capability
- **`Goal`**: Desired outcome or objective
- **`GuidingPrinciple`**: Design or architectural principle
- **`Requirement`**: Specific system need or constraint
- **`Capability`**: Observable system behavior
- **`UseCase`**: User interaction or workflow
- **`Scenario`**: Concrete instance of a use case
- **`DesignArtifact`**: Design decision or architectural element
- **`Decision`**: Architectural or design decision
- **`Constraint`**: System limitation or restriction
- **`Component`**: System module or architectural component
- **`Dependency`**: External system, library, or service
- **`DocumentationArtifact`**: Documentation or explanatory content

### Traceability Models (`models/traceability.py`)

Explicit traceability chains between layers:

- **`GoalRequirementTrace`**: Goal → Requirements
- **`RequirementCapabilityTrace`**: Requirement → Capabilities
- **`CapabilityComponentTrace`**: Capability → Components
- **`ComponentDependencyTrace`**: Component → Dependencies

### Integrity Rules (`models/rules.py`)

Machine-readable constraints for graph validation:

- **`IntegrityRule`**: Defines structural constraints (e.g., "every goal must have ≥1 requirement")
- **`RuleType`**: Types of validation checks (minimum_outgoing_edge_count, exact_outgoing_edge_count, etc.)
- **`Severity`**: Violation severity levels (low, medium, high)

### Query Patterns (`models/queries.py`)

Reusable AI reasoning tools for graph analysis:

- **`GraphQueryPattern`**: Defines queries for gap detection, completeness checks, impact analysis
- **`EdgeCheck`**: Checks for presence/absence of edges
- **`TraversalSpec`**: Defines graph traversal for impact analysis
- **`PathStep`**: Single step in a lineage trace pattern
- **`QueryIntent`**: Purpose of query (gap_detection, orphan_detection, lineage_trace, etc.)

### Assessment Models (`models/assessment.py`)

Structured output format for AI findings:

- **`Assessment`**: AI-generated finding about graph gaps or inconsistencies
- **`AssessmentType`**: Types of issues (missing_goal_coverage, orphan_decision, etc.)
- **`Confidence`**: AI confidence level (low, medium, high)

## Example Data

The `examples/ontology_data.py` module provides example data from WHITEBOARD_ONTOLOGY.md:

```python
from conversation_engine.examples.ontology_data import (
    get_goals,
    get_requirements,
    get_capabilities,
    get_components,
    get_goal_requirement_traces,
    get_sample_integrity_rules,
    get_sample_query_patterns,
)

# Load all goals from the ontology
goals = get_goals()

# Load traceability data
traces = get_goal_requirement_traces()

# Load integrity rules
rules = get_sample_integrity_rules()
```

## Usage

### Creating Nodes

```python
from conversation_engine.models import Goal, Requirement, Component

goal = Goal(
    id="goal-structured-convergence",
    name="Structured Convergence",
    statement="Enable the system to transform ambiguous human input into structured artifacts."
)

requirement = Requirement(
    id="REQ-001",
    name="Advisory Conversation Support",
    requirement_type="functional"
)

component = Component(
    id="component-artifact-synthesizer",
    name="Artifact Synthesizer",
    description="Synthesizes structured artifacts from conversation"
)
```

### Creating Traceability

```python
from conversation_engine.models import GoalRequirementTrace

trace = GoalRequirementTrace(
    goal_id="goal-structured-convergence",
    requirement_ids=["REQ-001", "REQ-004", "REQ-005"]
)
```

### Defining Integrity Rules

```python
from conversation_engine.models import IntegrityRule

rule = IntegrityRule(
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
)
```

### Defining Query Patterns

```python
from conversation_engine.models import GraphQueryPattern, EdgeCheck

query = GraphQueryPattern(
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
)
```

## Testing

Run the test suite:

```bash
/opt/miniforge3/envs/langgraph-sandbox/bin/python -m pytest tests/conversation_engine/ -v
```

All models are validated with comprehensive tests covering:
- Node creation and serialization
- Traceability relationships
- Integrity rule definitions
- Query pattern specifications
- Assessment output formats
- Example data loading

## Next Steps

This model layer provides the foundation for:

1. **Graph storage**: Persist nodes and edges in a graph database
2. **Validation engine**: Evaluate integrity rules against graph state
3. **Query engine**: Execute query patterns to detect gaps and issues
4. **AI reasoning**: Enable AI to assess architectural completeness
5. **Conversation orchestration**: Build the conversation subgraph that uses these models

## Design Rationale

### Why Pydantic over TypedDict?

- **Validation**: Pydantic validates data at runtime
- **Serialization**: Built-in JSON serialization/deserialization
- **Documentation**: Field descriptions become part of the schema
- **Type safety**: Stricter than TypedDict with better IDE support
- **Immutability**: Can freeze models where appropriate (rules, edges)

### Why separate traceability models?

Traceability is explicit and queryable, not implicit in node references. This enables:
- Gap detection (goals with no requirements)
- Coverage analysis (requirements with no capabilities)
- Impact analysis (what components are affected by a decision)
- Lineage tracing (goal → requirement → capability → component)

### Why frozen rules and edges?

- **Rules** are design-time artifacts that should not change at runtime
- **Edges** represent immutable relationships (create new edges instead of modifying)
- **Nodes** are mutable because their content evolves during conversation

## Architecture Alignment

These models directly implement the ontology layers from WHITEBOARD_ONTOLOGY.md:

1. **Intent Layer** → Goal, GuidingPrinciple, Feature
2. **Requirement Layer** → Requirement
3. **Behavior Layer** → Capability, UseCase, Scenario
4. **Design Knowledge Layer** → DesignArtifact, Decision, Constraint
5. **Design Layer** → Component, Dependency, DocumentationArtifact
6. **Traceability Layer** → *Trace models
7. **Integrity Rules Layer** → IntegrityRule
8. **Query Patterns Layer** → GraphQueryPattern
9. **Assessment Layer** → Assessment
