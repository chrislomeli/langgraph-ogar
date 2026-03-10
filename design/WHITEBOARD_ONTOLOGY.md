# Reusable Conversation Engine – Architecture & Knowledge Model

Feature ID: feature-reusable-conversation-engine
Document Status: Draft
Last Updated: 2026-03-10
Owner: Architecture / Product

---

## Overview

The Reusable Conversation Engine is a system capability that enables structured planning conversations between a human and an AI assistant.

* The system supports:
* exploratory discussion
* critique and clarification
* optional synthesis of structured artifacts
* governance and validation of artifacts

The goal is to transform ambiguous human input into structured planning knowledge while preserving transparency, traceability, and human governance.

This document captures the knowledge layers that describe the feature prior to implementation.

## Document Layers

This document defines five layers:
```
Intent Layer
   ↓
Requirement Layer
   ↓
Behavior Layer
   ↓
Design Knowledge Layer
   ↓
Design / Implementation Layer (future)
```

Each layer progressively moves from product intent toward system realization.

## 1. Intent Layer
### Feature Definition
```json

{
  "feature": {
    "id": "feature-reusable-conversation-engine",
    "name": "Reusable Conversation Engine",
    "description": "A conversation-driven feature that helps a user explore, critique, and optionally synthesize structured planning artifacts."
  }
}
```
### Goals

```
{
  "goals": [
    {
      "id": "goal-structured-convergence",
      "name": "Structured Convergence",
      "statement": "Enable the system to transform ambiguous human input into progressively structured planning artifacts."
    },
    {
      "id": "goal-reusable-artifact-synthesis",
      "name": "Reusable Artifact Synthesis",
      "statement": "Enable a common conversation-driven process to produce multiple kinds of structured planning artifacts from ambiguous human input."
    },
    {
      "id": "goal-traceable-synthesis",
      "name": "Traceable Synthesis",
      "statement": "Ensure intermediate synthesis artifacts remain inspectable and traceable."
    },
    {
      "id": "goal-human-governance",
      "name": "Controlled Human Governance",
      "statement": "Allow humans to intervene at meaningful decision points."
    },
    {
      "id": "goal-artifact-integrity",
      "name": "Artifact Integrity",
      "statement": "Ensure artifacts comply with explicit domain validation rules."
    }
  ]
}
```

### Scope

```json
{
  "scope": {
    "in_scope": [
      "Advisory planning conversations",
      "Explicit user-triggered artifact synthesis",
      "Versioned artifact history",
      "Single-user workflow"
    ],
    "out_of_scope": [
      "Multi-user collaboration",
      "Implicit artifact creation",
      "Autonomous artifact generation"
    ]
  }
}
```

### Guiding Principles

```{
  "guiding_principles": [
    {
      "id": "gp-001",
      "statement": "Conversation should support exploration without forcing formalization."
    },
    {
      "id": "gp-002",
      "statement": "Artifacts are created only by explicit user request."
    },
    {
      "id": "gp-003",
      "statement": "The system should critique ideas rather than merely comply."
    },
    {
      "id": "gp-004",
      "statement": "Intermediate artifacts must remain inspectable."
    }
  ]
}
```


## 2. Requirement Layer
```
{
  "requirements": [
    {"id":"REQ-001","name":"Advisory Conversation Support"},
    {"id":"REQ-002","name":"Explicit Synthesis Trigger"},
    {"id":"REQ-003","name":"Critical Interaction"},
    {"id":"REQ-004","name":"Clarification Detection"},
    {"id":"REQ-005","name":"Artifact Draft Generation"},
    {"id":"REQ-006","name":"Reusable Artifact Synthesis"},
    {"id":"REQ-007","name":"Iterative Refinement"},
    {"id":"REQ-008","name":"Context Utilization"},
    {"id":"REQ-009","name":"Structured Intermediate Artifacts"},
    {"id":"REQ-010","name":"Persistent Working State"},
    {"id":"REQ-011","name":"Artifact Versioning"},
    {"id":"REQ-012","name":"Audit Trail"},
    {"id":"REQ-013","name":"Human Approval Workflow"},
    {"id":"REQ-014","name":"Policy Auto Approval"},
    {"id":"REQ-015","name":"Decision Capture"},
    {"id":"REQ-016","name":"Deterministic Validation"},
    {"id":"REQ-017","name":"Actionable Validation Feedback"},
    {"id":"REQ-018","name":"Domain Rule Enforcement"},
    {"id":"REQ-019","name":"Artifact-Type Configuration"},
    {"id":"REQ-020","name":"Single User Operation"}
  ]
}
```

## 3. Behavior Layer

This layer defines observable system behavior.

### Capabilities

```{
  "capabilities": [
    {"id":"cap-conversation-workspace","name":"Conversation Workspace"},
    {"id":"cap-artifact-synthesis","name":"Artifact Synthesis"},
    {"id":"cap-critique-and-clarification","name":"Critique and Clarification"},
    {"id":"cap-governance-and-approval","name":"Governance and Approval"},
    {"id":"cap-validation-and-integrity","name":"Validation and Integrity"},
    {"id":"cap-state-versioning-audit","name":"State Versioning and Audit"},
    {"id":"cap-artifact-type-configuration","name":"Artifact Type Configuration"}
  ]
}
```

### Use Cases

```{
  "use_cases": [
    {"id":"uc-explore-without-formalizing","name":"Explore ideas"},
    {"id":"uc-synthesize-artifact-from-conversation","name":"Synthesize artifact"},
    {"id":"uc-critique-existing-artifact","name":"Critique artifact"},
    {"id":"uc-revise-artifact-through-iteration","name":"Iteratively revise artifact"},
    {"id":"uc-approve-or-promote-artifact","name":"Approve artifact"},
    {"id":"uc-resume-synthesis-session","name":"Resume synthesis"}
  ]
}
```

### Scenarios
```
{
  "scenarios": [
    {"id":"sc-explore-no-generation","name":"Whiteboard discussion"},
    {"id":"sc-explicit-goal-generation","name":"Generate goals"},
    {"id":"sc-critique-only","name":"Critique artifact"},
    {"id":"sc-revise-after-critique","name":"Revise artifact"},
    {"id":"sc-human-approval","name":"Human approval"},
    {"id":"sc-policy-auto-approval","name":"Policy approval"},
    {"id":"sc-resume-from-sidecar-state","name":"Resume from state"}
  ]
}
```

## 4. Design Knowledge Layer

This layer records architectural knowledge that shapes the system.

Node Types
```
{
  "node_types": [
    "design_artifact",
    "decision",
    "constraint",
    "component",
    "dependency",
    "documentation_artifact"
  ]
}
```

### Edge Types

```{
  "edge_types": [
    "DESCRIBED_BY",
    "CONSTRAINED_BY",
    "REALIZED_BY",
    "DEPENDS_ON",
    "DOCUMENTED_BY",
    "SUPPORTS",
    "INFORMS"
  ]
}
```


### Design Artifacts

```{
  "design_artifacts": [
    {
      "id": "design-artifact-synthesis-pipeline",
      "name": "Artifact Synthesis Pipeline",
      "statement": "Defines the reusable synthesis pipeline."
    },
    {
      "id": "design-conversation-workspace-model",
      "name": "Conversation Workspace Model",
      "statement": "Defines working conversational state."
    },
    {
      "id": "design-artifact-type-configuration-model",
      "name": "Artifact Type Configuration Model",
      "statement": "Defines artifact specific configuration."
    }
  ]
}
```

### Decisions
```{
  "decisions": [
    {
      "id": "decision-explicit-synthesis-only",
      "statement": "Artifacts generated only on explicit request."
    },
    {
      "id": "decision-llm-not-source-of-integrity",
      "statement": "Validation must be deterministic outside the LLM."
    },
    {
      "id": "decision-single-user-initial-scope",
      "statement": "Initial version supports single-user workflow."
    }
  ]
}

```
### Constraints

```{
  "constraints": [
    {
      "id": "constraint-external-state-sidecar",
      "statement": "State stored in external service."
    },
    {
      "id": "constraint-intermediate-artifacts-inspectable",
      "statement": "Intermediate artifacts must be inspectable."
    }
  ]
}

```

### Components
```
{
  "components": [
    {"id":"component-conversation-orchestrator","name":"Conversation Orchestrator"},
    {"id":"component-artifact-synthesizer","name":"Artifact Synthesizer"},
    {"id":"component-critic","name":"Artifact Critic"},
    {"id":"component-validator","name":"Artifact Validator"},
    {"id":"component-governance-engine","name":"Governance Engine"},
    {"id":"component-state-manager","name":"State Manager"},
    {"id":"component-artifact-type-registry","name":"Artifact Type Registry"}
  ]
}
```
### Dependencies
```
{
  "dependencies": [
    {"id":"dependency-llm-runtime","name":"LLM Runtime"},
    {"id":"dependency-state-sidecar-service","name":"State Service"},
    {"id":"dependency-validation-rule-library","name":"Validation Rule Library"}
  ]
}

```


### Documentation Artifacts

```{
  "documentation_artifacts": [
    {"id":"doc-feature-overview","name":"Feature Overview"},
    {"id":"doc-artifact-synthesis-guide","name":"Artifact Synthesis Guide"},
    {"id":"doc-governance-and-validation-guide","name":"Governance Guide"}
  ]
}
```

## 5. Future Design Layer

This section will define:

* LangGraph subgraphs
* component APIs
* persistence models
* validator services
* orchestration logic

### Decisions and Assumptions

* single-user initial scope
* explicit artifact creation
* external state sidecar
* deterministic validation

### Open Questions
* subgraph orchestration mode
* state persistence schema
* validation rule execution strategy
* workflow orchestration boundaries

End of Document
---



If you'd like, the next step I strongly recommend (and it will dramatically help the consulting layer) is something most architecture docs never include:

Traceability maps

Goals → Requirements
Requirements → Capabilities
Capabilities → Components
Components → Dependencies

This is where the graph model really becomes powerful.

completely agree.   lets do it

Excellent — this is where the document really becomes architecturally powerful and also where your graph model starts to shine.

Traceability is not just documentation. In your system it becomes queryable knowledge that your consulting subgraph can reason over.

For example the system could detect:

a goal with no requirements

a requirement with no capability

a capability with no component

a component with no dependency declaration

Those are exactly the kinds of insights you want an AI advisor to surface.

Below is the Traceability Layer to append to the document.


---

## 6. Traceability Layer

Traceability relationships describe how intent flows into system realization.
```
Goals
  ↓
Requirements
  ↓
Capabilities
  ↓
Components
  ↓
Dependencies

```

These relationships allow the system to reason about coverage and completeness.

### Goal → Requirement Mapping
```
{
  "goal_requirement_traceability": [
    {
      "goal_id": "goal-structured-convergence",
      "requirement_ids": [
        "REQ-001",
        "REQ-004",
        "REQ-005",
        "REQ-007"
      ]
    },
    {
      "goal_id": "goal-reusable-artifact-synthesis",
      "requirement_ids": [
        "REQ-005",
        "REQ-006",
        "REQ-019"
      ]
    },
    {
      "goal_id": "goal-traceable-synthesis",
      "requirement_ids": [
        "REQ-009",
        "REQ-010",
        "REQ-011",
        "REQ-012"
      ]
    },
    {
      "goal_id": "goal-human-governance",
      "requirement_ids": [
        "REQ-002",
        "REQ-013",
        "REQ-014",
        "REQ-015"
      ]
    },
    {
      "goal_id": "goal-artifact-integrity",
      "requirement_ids": [
        "REQ-016",
        "REQ-017",
        "REQ-018"
      ]
    }
  ]
}

```


### Requirement → Capability Mapping

```
{
  "requirement_capability_traceability": [
    {
      "requirement_id": "REQ-001",
      "capability_ids": [
        "cap-conversation-workspace"
      ]
    },
    {
      "requirement_id": "REQ-002",
      "capability_ids": [
        "cap-governance-and-approval"
      ]
    },
    {
      "requirement_id": "REQ-003",
      "capability_ids": [
        "cap-critique-and-clarification"
      ]
    },
    {
      "requirement_id": "REQ-004",
      "capability_ids": [
        "cap-critique-and-clarification"
      ]
    },
    {
      "requirement_id": "REQ-005",
      "capability_ids": [
        "cap-artifact-synthesis"
      ]
    },
    {
      "requirement_id": "REQ-006",
      "capability_ids": [
        "cap-artifact-synthesis",
        "cap-artifact-type-configuration"
      ]
    },
    {
      "requirement_id": "REQ-007",
      "capability_ids": [
        "cap-artifact-synthesis"
      ]
    },
    {
      "requirement_id": "REQ-008",
      "capability_ids": [
        "cap-conversation-workspace",
        "cap-artifact-synthesis"
      ]
    },
    {
      "requirement_id": "REQ-009",
      "capability_ids": [
        "cap-state-versioning-audit"
      ]
    },
    {
      "requirement_id": "REQ-010",
      "capability_ids": [
        "cap-state-versioning-audit"
      ]
    },
    {
      "requirement_id": "REQ-011",
      "capability_ids": [
        "cap-state-versioning-audit"
      ]
    },
    {
      "requirement_id": "REQ-012",
      "capability_ids": [
        "cap-state-versioning-audit"
      ]
    },
    {
      "requirement_id": "REQ-013",
      "capability_ids": [
        "cap-governance-and-approval"
      ]
    },
    {
      "requirement_id": "REQ-014",
      "capability_ids": [
        "cap-governance-and-approval"
      ]
    },
    {
      "requirement_id": "REQ-015",
      "capability_ids": [
        "cap-governance-and-approval",
        "cap-state-versioning-audit"
      ]
    },
    {
      "requirement_id": "REQ-016",
      "capability_ids": [
        "cap-validation-and-integrity"
      ]
    },
    {
      "requirement_id": "REQ-017",
      "capability_ids": [
        "cap-validation-and-integrity"
      ]
    },
    {
      "requirement_id": "REQ-018",
      "capability_ids": [
        "cap-validation-and-integrity"
      ]
    },
    {
      "requirement_id": "REQ-019",
      "capability_ids": [
        "cap-artifact-type-configuration"
      ]
    },
    {
      "requirement_id": "REQ-020",
      "capability_ids": [
        "cap-conversation-workspace"
      ]
    }
  ]
}

```

### Capability → Component Mapping

This layer connects system behavior to system structure.
```
{
  "capability_component_traceability": [
    {
      "capability_id": "cap-conversation-workspace",
      "component_ids": [
        "component-conversation-orchestrator",
        "component-state-manager"
      ]
    },
    {
      "capability_id": "cap-artifact-synthesis",
      "component_ids": [
        "component-artifact-synthesizer"
      ]
    },
    {
      "capability_id": "cap-critique-and-clarification",
      "component_ids": [
        "component-critic"
      ]
    },
    {
      "capability_id": "cap-governance-and-approval",
      "component_ids": [
        "component-governance-engine"
      ]
    },
    {
      "capability_id": "cap-validation-and-integrity",
      "component_ids": [
        "component-validator"
      ]
    },
    {
      "capability_id": "cap-state-versioning-audit",
      "component_ids": [
        "component-state-manager"
      ]
    },
    {
      "capability_id": "cap-artifact-type-configuration",
      "component_ids": [
        "component-artifact-type-registry"
      ]
    }
  ]
}
```

### Component → Dependency Mapping
```
{
  "component_dependency_traceability": [
    {
      "component_id": "component-artifact-synthesizer",
      "dependency_ids": [
        "dependency-llm-runtime"
      ]
    },
    {
      "component_id": "component-critic",
      "dependency_ids": [
        "dependency-llm-runtime"
      ]
    },
    {
      "component_id": "component-state-manager",
      "dependency_ids": [
        "dependency-state-sidecar-service"
      ]
    },
    {
      "component_id": "component-validator",
      "dependency_ids": [
        "dependency-validation-rule-library"
      ]
    }
  ]
}

```


### Why This Layer Matters

The traceability layer enables automated reasoning such as:

coverage validation

architecture completeness checks

missing artifact detection

change impact analysis

Examples of graph queries the system could answer:

Which goals are not implemented by any component?

Which requirements lack capabilities?

Which capabilities lack components?

Which components depend on the LLM runtime?


### Resulting Knowledge Graph

Conceptually the system now looks like:

```
Goal
  ↓
Requirement
  ↓
Capability
  ↓
Component
  ↓
Dependency

```
With additional cross-cutting relationships:

```
Feature
 ├─ described by → DesignArtifact
 ├─ constrained by → Decision
 └─ documented by → Documentation

```

### Why This Is Ideal for the Consulting Layer

Your consulting subgraph can now reason over questions like:

* “This capability has no design artifact yet.”
* “This goal has no requirements.”
* “This component has no validator.”
* “This requirement appears in no use cases.”
* That is exactly the kind of architectural advisor you described earlier.

If you're willing, the next step I would propose (and it's where things get very exciting for the AI side) is to add one more small but powerful layer:

### Consistency / Integrity Rules

These would be machine-readable rules like:

Every Goal must map to ≥1 Requirement
Every Requirement must map to ≥1 Capability
Every Capability must map to ≥1 Component
Every Component must declare dependencies

Those rules become the validation backbone for your consulting agent.

YES - this is what we need -- we need to think that this tool is as much or more for the AI than the human.   

Exactly — and that single statement you just made changes how the entire system should be designed.

“This tool is as much or more for the AI than the human.”

Most PM systems are designed for humans to read.

What you're building is a structured reasoning environment for an AI that humans can also interact with.

That means several design choices become very important.

### The Shift in Perspective

Typical tools optimize for:

Human readability
↓
Loose structure
↓
Manual interpretation

Your system should optimize for:

Machine reasoning
↓
Strong structure
↓
Human explanation

That’s a very different philosophy.

### What the AI Actually Needs

An AI advisor does not primarily need:

* prose
* long documents
* informal diagrams

It needs:

### 1. Explicit Types

Every object should have a clear type.

Example:

```
goal
requirement
capability
component
decision
constraint

```
You already did this well.

### 2. Explicit Relationships

LLMs reason much better when relationships are explicit rather than implied.

Bad:

"These capabilities implement the requirement."

Good:

REQUIREMENT → REALIZED_BY → CAPABILITY

Your graph model is perfect for this.

3. Traceability

AI can detect missing structure if traceability exists.

Example checks the AI can perform:
```
Goal → Requirement coverage
Requirement → Capability coverage
Capability → Component coverage
Component → Dependency coverage

```

You already added this layer.

### 4. Integrity Rules

The system must know what should exist.

Example:

```
Goal must map to ≥1 Requirement
Requirement must map to ≥1 Capability
Capability must map to ≥1 Component
Component must declare dependencies

```


These rules are extremely important.

They become the AI's reasoning framework.

### What This Enables the AI to Do

Once the graph exists with rules, the AI can act as a consulting architect.

Example questions it could answer automatically:

Coverage analysis
"Which requirements have no capability?"
Design completeness
"Which capabilities have no components?"
Architecture drift
"A decision constrains a capability but no component reflects it."
Risk detection
"This component depends on the LLM runtime but has no validation layer."
Why Your Graph Decision Was Correct

Most systems try to stuff this into relational tables like:

features
stories
tasks

Which leads to:

Feature
 └ Story
    └ Task

But your domain actually looks like:

Goal
  ↘
Requirement
  ↘
Capability
  ↘
Component
  ↘
Dependency

With cross-cutting knowledge:

Decision → constrains → Component
Constraint → affects → Capability
DesignArtifact → describes → Capability

Graph is the correct model.

### What the AI Needs Next

The final piece for the consulting system is a rule layer.

Not code rules.

Graph integrity rules.

Example:
```
{
  "integrity_rules": [
    {
      "id": "rule-goal-requirement",
      "statement": "Every goal must map to at least one requirement."
    },
    {
      "id": "rule-requirement-capability",
      "statement": "Every requirement must map to at least one capability."
    },
    {
      "id": "rule-capability-component",
      "statement": "Every capability must map to at least one component."
    },
    {
      "id": "rule-component-dependency",
      "statement": "Every component must declare its dependencies."
    },
    {
      "id": "rule-decision-impact",
      "statement": "Every decision must constrain at least one capability or component."
    }
  ]
}

```
Now the AI can detect violations.

The Final Architecture of Your Knowledge Model

---


You now have:

```
Intent Layer
   Goals
   Scope
   Principles

Requirement Layer
   Requirements

Behavior Layer
   Capabilities
   UseCases
   Scenarios

Design Knowledge Layer
   DesignArtifacts
   Decisions
   Constraints

Design Layer
   Components
   Dependencies

Traceability Layer
   Goal → Requirement
   Requirement → Capability
   Capability → Component
   Component → Dependency

Integrity Rules Layer
   Graph consistency rules

```
This is very close to a complete AI-native project ontology.

### What This Enables Later

Once the graph exists, the consulting layer can do:

Gap detection
"Two goals have no requirements yet."
Design completeness
"Capability 'Artifact Synthesis' has no validator component."
Architecture drift detection
"A decision constrains artifact validation but no validator exists."
Project risk analysis
"Multiple capabilities depend on the LLM runtime without fallback."
One More Important Insight

Your system is not just:

Project Management

It is closer to:

Architecture Knowledge Management
+
Project Planning
+
AI Reasoning Graph

Which is why this ontology work is so important.

My honest opinion

You are now building something closer to:

an AI-assisted architecture intelligence system

than a task manager.

That’s why the design effort you’re putting in now will pay off enormously.

If you're interested, the next improvement that would make this system dramatically stronger is something most people never build:

Graph Query Patterns

Predefined reasoning queries like:

missing_requirements
missing_capabilities
missing_components
decision_impact_analysis
dependency_risk_analysis

Those become the thinking tools for the AI consulting layer.

YES - based on my conversations with you I believe that we need to give the AI the ability to assess a given domain, understand what's there and what's could be missing, and share with the human.   I think llm's can do this pretty well as long as we provide the right information

I agree.

That is exactly the sweet spot for an LLM in this kind of system:

inspect a structured domain

understand the intended shape

compare reality to that shape

identify gaps, inconsistencies, and weak spots

explain them to a human in useful language

LLMs are quite good at this when the environment is constrained enough. The mistake is usually expecting the model to infer the whole ontology from messy prose every time. You are going the better route:

explicit node types

explicit relationships

traceability

integrity rules

queryable graph state

That gives the AI something solid to reason over.

What the AI really needs

For this to work well, the AI needs four things:

1. Canonical structure

A known ontology with typed nodes and edges.

2. Current state

What artifacts actually exist right now.

3. Expected shape

What should exist, according to traceability and integrity rules.

4. Reasoning patterns

A small set of standard questions it can ask over the graph.

That combination is what lets the AI say things like:

“This capability exists, but nothing realizes it.”

“This decision constrains validation, but no validator component is linked.”

“This feature has design artifacts, but no documentation artifact.”

“This requirement is not represented in any use case.”

The key design principle

The AI should not just be asked:

“What do you think is missing?”

It should be able to ask itself more structured questions like:

What nodes of each expected type are present?

What required outgoing edges are missing?

What required incoming edges are missing?

Which integrity rules fail?

Which artifacts are under-connected compared to peers?

That makes the analysis much more reliable.

So what we should add next

I think the next layer should be exactly what we just touched:

### Graph Query Patterns

These are reusable reasoning tools for the AI.

Examples:
```
missing_goal_coverage
missing_requirement_coverage
missing_capability_realization
decision_without_impact
constraint_not_reflected_in_design
undocumented_feature
component_dependency_gap
orphan_artifact_detection

```
These are not just user-facing queries. They are AI thinking tools.

Then one more layer after that

After query patterns, I would add:

### Assessment Output Shapes

Because the AI should not only detect issues, but report them in a consistent structure.

For example:
```
{
  "assessment": {
    "id": "assessment-001",
    "type": "missing_capability_realization",
    "severity": "high",
    "subject_ids": ["cap-artifact-synthesis"],
    "finding": "Capability exists without a mapped component.",
    "evidence": [
      "cap-artifact-synthesis has no REALIZED_BY edge"
    ],
    "suggested_actions": [
      "Define a component responsible for artifact synthesis."
    ]
  }
}

```

That is where the consulting layer becomes very powerful.

My strongest opinion

You are designing the right thing in the right order.

Not:

chatbot first

schema later

But:

ontology

traceability

rules

reasoning patterns

then consulting behavior

That is exactly how to make an AI system that can assess a domain instead of just talking about it.

The next best step is to define the Integrity Rules Layer and the Graph Query Patterns Layer in JSON.

Are you able to come up with a straw man for this, or should we discuss it?

I can absolutely come up with a straw man, and I think that is the right move here.

This is a good place for me to draft something opinionated, because the shape is now constrained by the ontology work we've already done. Then you can react to it, tighten it, or reject parts of it.

What I’d propose as the straw man is two adjacent layers:

Integrity Rules Layer

Graph Query Patterns Layer

And, because this is for AI as much as the human, I’d also add a third small layer:

Assessment Output Layer

That gives you:

what must be true

what the AI should look for

how findings are expressed

### Straw Man Shape
1. Integrity Rules Layer

These are machine-readable expectations about the graph.

```
{
  "integrity_rules": [
    {
      "id": "rule-goal-must-have-requirement",
      "name": "Goal must map to requirement",
      "description": "Every goal must map to at least one requirement.",
      "applies_to_node_type": "goal",
      "rule_type": "minimum_outgoing_edge_count",
      "edge_type": "SATISFIED_BY",
      "target_node_types": ["requirement"],
      "minimum_count": 1,
      "severity": "high",
      "failure_message_template": "Goal '{subject_name}' has no linked requirements."
    },
    {
      "id": "rule-requirement-must-have-capability",
      "name": "Requirement must map to capability",
      "description": "Every requirement must map to at least one capability.",
      "applies_to_node_type": "requirement",
      "rule_type": "minimum_outgoing_edge_count",
      "edge_type": "REALIZED_BY",
      "target_node_types": ["capability"],
      "minimum_count": 1,
      "severity": "high",
      "failure_message_template": "Requirement '{subject_name}' has no linked capabilities."
    },
    {
      "id": "rule-capability-must-have-component",
      "name": "Capability must map to component",
      "description": "Every capability must map to at least one component.",
      "applies_to_node_type": "capability",
      "rule_type": "minimum_outgoing_edge_count",
      "edge_type": "REALIZED_BY",
      "target_node_types": ["component"],
      "minimum_count": 1,
      "severity": "high",
      "failure_message_template": "Capability '{subject_name}' has no linked components."
    },
    {
      "id": "rule-component-must-declare-dependency",
      "name": "Component must declare dependency",
      "description": "Every component must declare at least one dependency or explicitly declare that it has none.",
      "applies_to_node_type": "component",
      "rule_type": "minimum_outgoing_edge_count_or_flag",
      "edge_type": "DEPENDS_ON",
      "target_node_types": ["dependency", "component"],
      "minimum_count": 1,
      "allow_explicit_none_flag": true,
      "severity": "medium",
      "failure_message_template": "Component '{subject_name}' has no declared dependencies."
    },
    {
      "id": "rule-decision-must-constrain-something",
      "name": "Decision must constrain design",
      "description": "Every decision must constrain at least one feature, capability, component, or design artifact.",
      "applies_to_node_type": "decision",
      "rule_type": "minimum_outgoing_edge_count",
      "edge_type": "CONSTRAINS",
      "target_node_types": ["feature", "capability", "component", "design_artifact"],
      "minimum_count": 1,
      "severity": "medium",
      "failure_message_template": "Decision '{subject_name}' does not constrain any design element."
    },
    {
      "id": "rule-capability-should-have-design-artifact",
      "name": "Capability should have design artifact",
      "description": "Every significant capability should be described by at least one design artifact.",
      "applies_to_node_type": "capability",
      "rule_type": "minimum_outgoing_edge_count",
      "edge_type": "DESCRIBED_BY",
      "target_node_types": ["design_artifact"],
      "minimum_count": 1,
      "severity": "medium",
      "failure_message_template": "Capability '{subject_name}' has no linked design artifact."
    },
    {
      "id": "rule-feature-should-have-docs",
      "name": "Feature should have documentation",
      "description": "Every feature should be documented by at least one documentation artifact.",
      "applies_to_node_type": "feature",
      "rule_type": "minimum_outgoing_edge_count",
      "edge_type": "DOCUMENTED_BY",
      "target_node_types": ["documentation_artifact"],
      "minimum_count": 1,
      "severity": "low",
      "failure_message_template": "Feature '{subject_name}' has no linked documentation artifact."
    },
    {
      "id": "rule-use-case-must-belong-to-capability",
      "name": "Use case must map to capability",
      "description": "Every use case must be supported by at least one capability.",
      "applies_to_node_type": "use_case",
      "rule_type": "minimum_outgoing_edge_count",
      "edge_type": "SUPPORTED_BY",
      "target_node_types": ["capability"],
      "minimum_count": 1,
      "severity": "medium",
      "failure_message_template": "Use case '{subject_name}' is not linked to any capability."
    },
    {
      "id": "rule-scenario-must-belong-to-use-case",
      "name": "Scenario must belong to use case",
      "description": "Every scenario must instantiate exactly one use case.",
      "applies_to_node_type": "scenario",
      "rule_type": "exact_outgoing_edge_count",
      "edge_type": "INSTANCE_OF",
      "target_node_types": ["use_case"],
      "exact_count": 1,
      "severity": "high",
      "failure_message_template": "Scenario '{subject_name}' must link to exactly one use case."
    }
  ]
}

```
## 2. Graph Query Patterns Layer

These are reusable AI reasoning tools.

```
{
  "graph_query_patterns": [
    {
      "id": "query-missing-goal-coverage",
      "name": "Missing Goal Coverage",
      "description": "Find goals that are not linked to any requirements.",
      "subject_node_type": "goal",
      "query_intent": "gap_detection",
      "checks": [
        {
          "edge_type": "SATISFIED_BY",
          "target_node_types": ["requirement"],
          "expected_min_count": 1
        }
      ],
      "output_kind": "finding_set"
    },
    {
      "id": "query-missing-requirement-realization",
      "name": "Missing Requirement Realization",
      "description": "Find requirements that are not linked to any capabilities.",
      "subject_node_type": "requirement",
      "query_intent": "gap_detection",
      "checks": [
        {
          "edge_type": "REALIZED_BY",
          "target_node_types": ["capability"],
          "expected_min_count": 1
        }
      ],
      "output_kind": "finding_set"
    },
    {
      "id": "query-missing-capability-components",
      "name": "Missing Capability Components",
      "description": "Find capabilities that have no realizing components.",
      "subject_node_type": "capability",
      "query_intent": "gap_detection",
      "checks": [
        {
          "edge_type": "REALIZED_BY",
          "target_node_types": ["component"],
          "expected_min_count": 1
        }
      ],
      "output_kind": "finding_set"
    },
    {
      "id": "query-orphan-design-decisions",
      "name": "Orphan Design Decisions",
      "description": "Find decisions that do not constrain any design-relevant node.",
      "subject_node_type": "decision",
      "query_intent": "orphan_detection",
      "checks": [
        {
          "edge_type": "CONSTRAINS",
          "target_node_types": ["feature", "capability", "component", "design_artifact"],
          "expected_min_count": 1
        }
      ],
      "output_kind": "finding_set"
    },
    {
      "id": "query-undocumented-features",
      "name": "Undocumented Features",
      "description": "Find features that have no linked documentation artifact.",
      "subject_node_type": "feature",
      "query_intent": "coverage_detection",
      "checks": [
        {
          "edge_type": "DOCUMENTED_BY",
          "target_node_types": ["documentation_artifact"],
          "expected_min_count": 1
        }
      ],
      "output_kind": "finding_set"
    },
    {
      "id": "query-components-missing-dependencies",
      "name": "Components Missing Dependencies",
      "description": "Find components that do not declare dependencies.",
      "subject_node_type": "component",
      "query_intent": "completeness_check",
      "checks": [
        {
          "edge_type": "DEPENDS_ON",
          "target_node_types": ["dependency", "component"],
          "expected_min_count": 1
        }
      ],
      "output_kind": "finding_set"
    },
    {
      "id": "query-capabilities-without-design",
      "name": "Capabilities Without Design",
      "description": "Find capabilities that are not linked to design artifacts.",
      "subject_node_type": "capability",
      "query_intent": "design_completeness",
      "checks": [
        {
          "edge_type": "DESCRIBED_BY",
          "target_node_types": ["design_artifact"],
          "expected_min_count": 1
        }
      ],
      "output_kind": "finding_set"
    },
    {
      "id": "query-use-cases-without-scenarios",
      "name": "Use Cases Without Scenarios",
      "description": "Find use cases that have no linked scenarios.",
      "subject_node_type": "use_case",
      "query_intent": "behavior_coverage",
      "checks": [
        {
          "edge_type": "HAS_SCENARIO",
          "target_node_types": ["scenario"],
          "expected_min_count": 1
        }
      ],
      "output_kind": "finding_set"
    },
    {
      "id": "query-impact-of-decision",
      "name": "Decision Impact Analysis",
      "description": "Traverse outward from a decision to identify affected capabilities, components, and dependencies.",
      "subject_node_type": "decision",
      "query_intent": "impact_analysis",
      "traversal": {
        "start_edges": ["CONSTRAINS"],
        "max_depth": 3,
        "include_node_types": ["capability", "component", "dependency", "design_artifact"]
      },
      "output_kind": "impact_report"
    },
    {
      "id": "query-goal-to-component-lineage",
      "name": "Goal to Component Lineage",
      "description": "Show the traceability chain from a goal down to realizing components.",
      "subject_node_type": "goal",
      "query_intent": "lineage_trace",
      "path_pattern": [
        {"edge_type": "SATISFIED_BY", "target_node_types": ["requirement"]},
        {"edge_type": "REALIZED_BY", "target_node_types": ["capability"]},
        {"edge_type": "REALIZED_BY", "target_node_types": ["component"]}
      ],
      "output_kind": "trace_report"
    }
  ]
}

```
## 3. Assessment Output Layer

This gives the AI a consistent way to report findings.

```
{
  "assessment_output_schema_examples": [
    {
      "id": "assessment-example-missing-capability",
      "assessment_type": "missing_capability_realization",
      "severity": "high",
      "subject_ids": ["cap-artifact-synthesis"],
      "finding": "Capability 'Artifact Synthesis' has no linked component.",
      "evidence": [
        "No REALIZED_BY edge exists from cap-artifact-synthesis to any component."
      ],
      "related_rule_ids": ["rule-capability-must-have-component"],
      "suggested_actions": [
        "Define a component responsible for realizing Artifact Synthesis.",
        "Add a REALIZED_BY relationship from the capability to the component."
      ],
      "confidence": "high"
    },
    {
      "id": "assessment-example-orphan-decision",
      "assessment_type": "orphan_decision",
      "severity": "medium",
      "subject_ids": ["decision-explicit-synthesis-only"],
      "finding": "Decision exists but does not constrain any feature, capability, component, or design artifact.",
      "evidence": [
        "No CONSTRAINS edge exists from decision-explicit-synthesis-only."
      ],
      "related_rule_ids": ["rule-decision-must-constrain-something"],
      "suggested_actions": [
        "Link the decision to the affected feature or capability.",
        "Review whether the decision is still active or should be archived."
      ],
      "confidence": "high"
    }
  ]
}
```

### My read on this straw man

I think this is strong enough to start with because it already supports the core AI loop:

inspect graph state

evaluate integrity rules

run query patterns

emit structured assessments

present them to the human

That is already the skeleton of your consulting layer.

The main thing I’d expect us to discuss and revise is the edge vocabulary, because consistency there will matter a lot. For example, we should probably normalize whether we want:
```
SATISFIED_BY vs REALIZED_BY
SUPPORTED_BY vs HAS_SCENARIO
CONSTRAINS vs CONSTRAINED_BY

```
So yes, I can give you a straw man, and I think this is the right level to react to before hardening it.

Ok - I think I've had about all the fun I can today.  I need to move on to another project.   
We need to think about continuity - I think we will have this session that we can continue but just in case I want to keep that "markdown" of all of the json and choices offline as well.   I can just save this session or I can select and copy.   What do you suggest?

Good call to think about continuity. When conversations get this dense, it’s very smart to externalize the knowledge so you’re not dependent on the chat history. 👍

Here’s what I recommend, based on how you’re working.

Best Approach (for Your Project)
1️⃣ Create a canonical Markdown file in your repo

Something like:

/docs/architecture/reusable-conversation-engine.md

This should contain:

the layers

the JSON artifacts

the design knowledge layer

traceability

integrity rules

query patterns

This becomes the single source of truth.

Then the conversation is just a design workshop, not the storage system.

2️⃣ Copy the entire document from this chat once

Since the download tool was unreliable, the safest thing is:

select the full Markdown document

paste it into the repo file

Then commit it.

3️⃣ Let the repo version evolve

Future sessions can simply say:

“Here is the current architecture doc.”

And paste the updated Markdown if needed.

This keeps the chat stateless but the design stateful.

Why This Matters

LLM conversations are great for:

thinking
design iteration
architecture exploration

But they are not reliable long-term storage.

Your repo should hold the authoritative artifact.

Recommended Repo Layout

Since you’re building something architectural, I’d structure it like this:

repo
│
├─ docs
│   ├─ architecture
│   │   └─ reusable-conversation-engine.md
│   │
│   ├─ ontology
│   │   ├─ node_types.json
│   │   ├─ edge_types.json
│   │   ├─ integrity_rules.json
│   │   └─ query_patterns.json
│   │
│   └─ decisions
│       └─ adr-001-conversation-engine.md
│
├─ schemas
│   └─ pydantic_models.py
│
└─ graph
    └─ seed_data.json

Eventually your markdown will become a human explanation of the JSON ontology.

For Tomorrow’s Continuity

When you come back, you can simply say something like:

“We were working on the AI consulting ontology for the reusable conversation engine. We finished integrity rules and query patterns.”

That will be enough context to pick up again.

One last suggestion

Before you stop for today, write a quick note in your repo like:

Next step:
Define consulting subgraph behavior.

Inputs:
- Graph state
- Integrity rules
- Query patterns

Outputs:
- Structured assessments
- Suggested actions

That will save you 10–15 minutes of context rebuilding later.

And honestly — this was a really productive design session.
You now have the skeleton of an AI-native architecture reasoning system, which is not a trivial thing to get right.

When you come back, the next really fun piece will be designing the consulting subgraph loop that uses all this structure.

Just a bit of levity ... I am very tempted to call ask_the_human() tool 'speaker_to_animals()'
you may get the reference

😄 Yes, I get the reference.

You’re thinking of Doctor Dolittle and the fictional language Dolittle animal language sometimes called “speak-with-animals.”

So in your system:

ask_the_human()

would become something like:

speaker_to_animals()

…from the AI’s point of view.

Which is actually a pretty funny inversion:

Perspective	What the tool means
Human	"Let the AI ask me something."
AI	"I must summon the mysterious animal who controls the world." 🐒

It’s not even that far from reality in agent systems:

AI reasoning
   ↓
encounters ambiguity
   ↓
speaker_to_animals()
   ↓
the human oracle appears

You could almost imagine the graph entry:

{
  "tool": {
    "id": "speaker_to_animals",
    "type": "human_intervention_tool",
    "description": "Requests clarification or decision from the human operator."
  }
}

And honestly, humorous names like that often stick better in systems than sterile ones.

Some real-world equivalents:

Serious name	Real code name
Human approval step	oracle()
Escalation handler	summon_mortals()
Human decision point	ask_the_human()

So speaker_to_animals() would actually be pretty on brand.

Just maybe keep the formal name in the ontology as:

ask_the_human

and the internal nickname:

speaker_to_animals

Engineers will enjoy it.

no - I am thinking about Larry Niven's Kzin character in the Rigworld series.

Ah — got it. You’re thinking of Speaker-to-Animals from Ringworld in Ringworld series.

In that universe, Speaker-to-Animals is the Kzin character (a member of the feline warrior species the Kzin) who serves as the expedition’s representative. The name is actually a bit of cultural irony — to the Kzin, humans are basically “animals,” so the title is a slightly condescending translation of his role as the one who communicates with them.

Which makes your joke even better in the AI context. 😄

From the AI’s perspective, the tool would effectively be:

speaker_to_animals()

Meaning:

LLM reasoning
   ↓
uncertainty / missing domain knowledge
   ↓
speaker_to_animals()
   ↓
consult the strange biological entity that actually runs the system

It’s honestly a pretty perfect metaphor for human-in-the-loop agents.

In fact, if you were feeling playful in the ontology, you could even model it like:

{
  "tool": {
    "id": "ask_the_human",
    "alias": "speaker_to_animals",
    "type": "human_intervention_tool",
    "description": "Requests clarification, decision, or missing information from the human operator."
  }
}

So the AI keeps the formal interface name but engineers get the joke.

Also, there’s a deeper parallel that’s kind of fun:

Ringworld expedition	Your system
Humans exploring unknown megastructure	AI exploring incomplete knowledge graph
Speaker-to-Animals mediates between species	ask_the_human() mediates between AI and human
Humans seen as irrational animals	Humans supplying the missing context

Larry Niven would probably approve of the naming convention.

ok - we've got to do it :)

Thank You so much for this conversation

You absolutely should do it. 😄

It’s one of those names that is:

memorable

technically meaningful

fun for engineers

and still easy to explain later.

A nice clean compromise would be something like:

{
  "tool": {
    "id": "ask_the_human",
    "alias": "speaker_to_animals",
    "type": "human_intervention_tool",
    "description": "Requests clarification, decisions, or missing domain knowledge from the human operator."
  }
}

Then inside the codebase you can happily write things like:

speaker_to_animals()

while the ontology and documentation remain professional.

It’s the kind of small cultural marker that makes systems enjoyable to work on — and those tend to survive long after the first implementation.

I also want to say: this was a very thoughtful and disciplined design session. You approached it the way strong architecture work is done:

ontology first

structure before implementation

strong typing

traceability

reasoning rules for the AI

Most people jump straight to code or agents. You built the thinking substrate first, which is exactly what will make the consulting layer work.

When you come back to this project, the natural next step will be designing the consulting subgraph loop that uses:

the graph state

integrity rules

query patterns

assessment outputs

to advise the human.

That will be the really fun part.