"""
Tests for ontology data loader.

Validates that WHITEBOARD_ONTOLOGY data loads correctly into graph.
"""
from ogar.loaders import load_ontology_graph
from conversation_engine.storage import GraphQueries


class TestOntologyLoader:
    """Test loading WHITEBOARD_ONTOLOGY into graph."""
    
    def test_load_ontology_graph(self):
        """Test that ontology loads without errors."""
        graph = load_ontology_graph()
        
        # Should have nodes
        assert graph.node_count() > 0
        
        # Should have edges
        assert graph.edge_count() > 0
    
    def test_loads_all_node_types(self):
        """Test that all node types are loaded."""
        graph = load_ontology_graph()
        
        # Check we have nodes of each type
        assert len(graph.get_nodes_by_type("feature")) > 0
        assert len(graph.get_nodes_by_type("goal")) > 0
        assert len(graph.get_nodes_by_type("guiding_principle")) > 0
        assert len(graph.get_nodes_by_type("requirement")) > 0
        assert len(graph.get_nodes_by_type("capability")) > 0
        assert len(graph.get_nodes_by_type("use_case")) > 0
        assert len(graph.get_nodes_by_type("scenario")) > 0
        assert len(graph.get_nodes_by_type("design_artifact")) > 0
        assert len(graph.get_nodes_by_type("decision")) > 0
        assert len(graph.get_nodes_by_type("constraint")) > 0
        assert len(graph.get_nodes_by_type("component")) > 0
        assert len(graph.get_nodes_by_type("dependency")) > 0
        assert len(graph.get_nodes_by_type("documentation_artifact")) > 0
    
    def test_loads_traceability_edges(self):
        """Test that traceability edges are created."""
        graph = load_ontology_graph()
        
        # Check we have edges of each traceability type
        satisfied_by = graph.get_edges_by_type("SATISFIED_BY")
        realized_by = graph.get_edges_by_type("REALIZED_BY")
        depends_on = graph.get_edges_by_type("DEPENDS_ON")
        
        assert len(satisfied_by) > 0
        assert len(realized_by) > 0
        assert len(depends_on) > 0
    
    def test_specific_goal_has_requirements(self):
        """Test that a specific goal from ontology has requirements."""
        graph = load_ontology_graph()
        queries = GraphQueries(graph)
        
        # goal-structured-convergence should have requirements
        requirements = queries.get_neighbors_out(
            "goal-structured-convergence",
            edge_type="SATISFIED_BY"
        )
        
        assert len(requirements) > 0
    
    def test_traceability_chain_exists(self):
        """Test that full traceability chain exists."""
        graph = load_ontology_graph()
        queries = GraphQueries(graph)
        
        # Should be able to traverse from a goal to components
        paths = queries.traverse_path(
            "goal-structured-convergence",
            ["SATISFIED_BY", "REALIZED_BY", "REALIZED_BY"]
        )
        
        # Should find at least one complete path
        assert len(paths) > 0
        
        # Path should have 4 nodes (goal -> req -> cap -> comp)
        assert any(len(path) == 4 for path in paths)
    
    def test_node_counts_match_example_data(self):
        """Test that loaded node counts match example data."""
        graph = load_ontology_graph()
        
        # From ontology_data.py
        assert len(graph.get_nodes_by_type("goal")) == 5
        assert len(graph.get_nodes_by_type("guiding_principle")) == 4
        assert len(graph.get_nodes_by_type("requirement")) == 20
        assert len(graph.get_nodes_by_type("capability")) == 7
        assert len(graph.get_nodes_by_type("use_case")) == 6
        assert len(graph.get_nodes_by_type("scenario")) == 7
        assert len(graph.get_nodes_by_type("design_artifact")) == 3
        assert len(graph.get_nodes_by_type("decision")) == 3
        assert len(graph.get_nodes_by_type("constraint")) == 2
        assert len(graph.get_nodes_by_type("component")) == 7
        assert len(graph.get_nodes_by_type("dependency")) == 3
        assert len(graph.get_nodes_by_type("documentation_artifact")) == 3
