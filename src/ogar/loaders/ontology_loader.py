"""
Load WHITEBOARD_ONTOLOGY example data into a knowledge graph.

This utility creates a fully populated graph from the example data,
including all nodes, edges, and traceability relationships.
"""
from conversation_engine.storage import KnowledgeGraph
from conversation_engine.models.base import BaseEdge
from ogar.examples import (
    get_feature,
    get_goals,
    get_guiding_principles,
    get_requirements,
    get_capabilities,
    get_use_cases,
    get_scenarios,
    get_design_artifacts,
    get_decisions,
    get_constraints,
    get_components,
    get_dependencies,
    get_documentation_artifacts,
    get_goal_requirement_traces,
    get_requirement_capability_traces,
    get_capability_component_traces,
    get_component_dependency_traces,
)


def load_ontology_graph() -> KnowledgeGraph:
    """
    Load the complete WHITEBOARD_ONTOLOGY into a knowledge graph.
    
    This creates a graph with all nodes and edges from the ontology example data:
    - Feature, goals, principles, requirements
    - Capabilities, use cases, scenarios
    - Design artifacts, decisions, constraints
    - Components, dependencies, documentation
    - All traceability edges
    
    Returns:
        Fully populated KnowledgeGraph
    """
    graph = KnowledgeGraph()
    
    # Add all nodes
    _add_nodes(graph)
    
    # Add all edges from traceability
    _add_traceability_edges(graph)
    
    return graph


def _add_nodes(graph: KnowledgeGraph) -> None:
    """Add all nodes to the graph."""
    # Feature
    graph.add_node(get_feature())
    
    # Intent layer
    for goal in get_goals():
        graph.add_node(goal)
    
    for principle in get_guiding_principles():
        graph.add_node(principle)
    
    # Requirement layer
    for req in get_requirements():
        graph.add_node(req)
    
    # Behavior layer
    for cap in get_capabilities():
        graph.add_node(cap)
    
    for uc in get_use_cases():
        graph.add_node(uc)
    
    for scenario in get_scenarios():
        graph.add_node(scenario)
    
    # Design knowledge layer
    for artifact in get_design_artifacts():
        graph.add_node(artifact)
    
    for decision in get_decisions():
        graph.add_node(decision)
    
    for constraint in get_constraints():
        graph.add_node(constraint)
    
    # Design layer
    for component in get_components():
        graph.add_node(component)
    
    for dependency in get_dependencies():
        graph.add_node(dependency)
    
    for doc in get_documentation_artifacts():
        graph.add_node(doc)


def _add_traceability_edges(graph: KnowledgeGraph) -> None:
    """Add all traceability edges to the graph."""
    # Goal → Requirement
    for trace in get_goal_requirement_traces():
        for req_id in trace.requirement_ids:
            edge = BaseEdge(
                edge_type="SATISFIED_BY",
                source_id=trace.goal_id,
                target_id=req_id
            )
            graph.add_edge(edge)
    
    # Requirement → Capability
    for trace in get_requirement_capability_traces():
        for cap_id in trace.capability_ids:
            edge = BaseEdge(
                edge_type="REALIZED_BY",
                source_id=trace.requirement_id,
                target_id=cap_id
            )
            graph.add_edge(edge)
    
    # Capability → Component
    for trace in get_capability_component_traces():
        for comp_id in trace.component_ids:
            edge = BaseEdge(
                edge_type="REALIZED_BY",
                source_id=trace.capability_id,
                target_id=comp_id
            )
            graph.add_edge(edge)
    
    # Component → Dependency
    for trace in get_component_dependency_traces():
        for dep_id in trace.dependency_ids:
            edge = BaseEdge(
                edge_type="DEPENDS_ON",
                source_id=trace.component_id,
                target_id=dep_id
            )
            graph.add_edge(edge)
