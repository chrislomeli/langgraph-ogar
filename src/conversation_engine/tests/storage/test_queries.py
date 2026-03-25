"""
Tests for GraphQueries high-level operations.

These tests validate graph analysis patterns:
- Neighbor queries
- Orphan detection
- Path traversal
- Coverage analysis
"""
import pytest

from conversation_engine.models import Goal, Requirement, Capability, Component
from conversation_engine.models.base import BaseEdge
from conversation_engine.storage import KnowledgeGraph, GraphQueries


class TestNeighborQueries:
    """Test neighbor query operations."""
    
    def test_get_neighbors_out(self):
        """Test getting outgoing neighbors."""
        graph = KnowledgeGraph()
        queries = GraphQueries(graph)
        
        goal = Goal(id="goal-1", name="Goal", statement="Test")
        req1 = Requirement(id="req-1", name="Requirement 1")
        req2 = Requirement(id="req-2", name="Requirement 2")
        
        graph.add_node(goal)
        graph.add_node(req1)
        graph.add_node(req2)
        
        graph.add_edge(BaseEdge(edge_type="SATISFIED_BY", source_id="goal-1", target_id="req-1"))
        graph.add_edge(BaseEdge(edge_type="SATISFIED_BY", source_id="goal-1", target_id="req-2"))
        
        neighbors = queries.get_neighbors_out("goal-1")
        assert len(neighbors) == 2
        assert all(isinstance(n, Requirement) for n in neighbors)
    
    def test_get_neighbors_out_filtered_by_edge_type(self):
        """Test getting neighbors filtered by edge type."""
        graph = KnowledgeGraph()
        queries = GraphQueries(graph)
        
        comp = Component(id="comp-1", name="Component")
        dep = Component(id="dep-1", name="Dependency")
        other = Component(id="other-1", name="Other")
        
        graph.add_node(comp)
        graph.add_node(dep)
        graph.add_node(other)
        
        graph.add_edge(BaseEdge(edge_type="DEPENDS_ON", source_id="comp-1", target_id="dep-1"))
        graph.add_edge(BaseEdge(edge_type="INFORMS", source_id="comp-1", target_id="other-1"))
        
        depends_neighbors = queries.get_neighbors_out("comp-1", edge_type="DEPENDS_ON")
        assert len(depends_neighbors) == 1
        assert depends_neighbors[0].id == "dep-1"
    
    def test_get_neighbors_out_filtered_by_target_type(self):
        """Test getting neighbors filtered by target node type."""
        graph = KnowledgeGraph()
        queries = GraphQueries(graph)
        
        req = Requirement(id="req-1", name="Requirement")
        cap1 = Capability(id="cap-1", name="Capability 1")
        cap2 = Capability(id="cap-2", name="Capability 2")
        
        graph.add_node(req)
        graph.add_node(cap1)
        graph.add_node(cap2)
        
        graph.add_edge(BaseEdge(edge_type="REALIZED_BY", source_id="req-1", target_id="cap-1"))
        graph.add_edge(BaseEdge(edge_type="REALIZED_BY", source_id="req-1", target_id="cap-2"))
        
        cap_neighbors = queries.get_neighbors_out("req-1", target_type="capability")
        assert len(cap_neighbors) == 2
        assert all(isinstance(n, Capability) for n in cap_neighbors)
    
    def test_get_neighbors_in(self):
        """Test getting incoming neighbors."""
        graph = KnowledgeGraph()
        queries = GraphQueries(graph)
        
        goal1 = Goal(id="goal-1", name="Goal 1", statement="Test")
        goal2 = Goal(id="goal-2", name="Goal 2", statement="Test")
        req = Requirement(id="req-1", name="Requirement")
        
        graph.add_node(goal1)
        graph.add_node(goal2)
        graph.add_node(req)
        
        graph.add_edge(BaseEdge(edge_type="SATISFIED_BY", source_id="goal-1", target_id="req-1"))
        graph.add_edge(BaseEdge(edge_type="SATISFIED_BY", source_id="goal-2", target_id="req-1"))
        
        neighbors = queries.get_neighbors_in("req-1")
        assert len(neighbors) == 2
        assert all(isinstance(n, Goal) for n in neighbors)


class TestOrphanDetection:
    """Test orphan detection operations."""
    
    def test_find_orphans_no_outgoing(self):
        """Test finding nodes with no outgoing edges."""
        graph = KnowledgeGraph()
        queries = GraphQueries(graph)
        
        goal1 = Goal(id="goal-1", name="Goal 1", statement="Test")
        goal2 = Goal(id="goal-2", name="Goal 2", statement="Test")
        req = Requirement(id="req-1", name="Requirement")
        
        graph.add_node(goal1)
        graph.add_node(goal2)
        graph.add_node(req)
        
        # goal-1 has outgoing edge, goal-2 doesn't
        graph.add_edge(BaseEdge(edge_type="SATISFIED_BY", source_id="goal-1", target_id="req-1"))
        
        orphans = queries.find_orphans("goal", direction="out")
        assert len(orphans) == 1
        assert orphans[0].id == "goal-2"
    
    def test_find_orphans_no_incoming(self):
        """Test finding nodes with no incoming edges."""
        graph = KnowledgeGraph()
        queries = GraphQueries(graph)
        
        req1 = Requirement(id="req-1", name="Requirement 1")
        req2 = Requirement(id="req-2", name="Requirement 2")
        goal = Goal(id="goal-1", name="Goal", statement="Test")
        
        graph.add_node(req1)
        graph.add_node(req2)
        graph.add_node(goal)
        
        # req-1 has incoming edge, req-2 doesn't
        graph.add_edge(BaseEdge(edge_type="SATISFIED_BY", source_id="goal-1", target_id="req-1"))
        
        orphans = queries.find_orphans("requirement", direction="in")
        assert len(orphans) == 1
        assert orphans[0].id == "req-2"
    
    def test_find_nodes_missing_edge_type(self):
        """Test finding nodes missing a specific edge type."""
        graph = KnowledgeGraph()
        queries = GraphQueries(graph)
        
        goal1 = Goal(id="goal-1", name="Goal 1", statement="Test")
        goal2 = Goal(id="goal-2", name="Goal 2", statement="Test")
        goal3 = Goal(id="goal-3", name="Goal 3", statement="Test")
        req = Requirement(id="req-1", name="Requirement")
        
        graph.add_node(goal1)
        graph.add_node(goal2)
        graph.add_node(goal3)
        graph.add_node(req)
        
        # goal-1 has SATISFIED_BY edge, goal-2 and goal-3 don't
        graph.add_edge(BaseEdge(edge_type="SATISFIED_BY", source_id="goal-1", target_id="req-1"))
        
        # goal-2 has different edge type
        graph.add_edge(BaseEdge(edge_type="INFORMS", source_id="goal-2", target_id="req-1"))
        
        missing = queries.find_nodes_missing_edge_type("goal", "SATISFIED_BY", direction="out")
        assert len(missing) == 2
        assert {n.id for n in missing} == {"goal-2", "goal-3"}


class TestPathTraversal:
    """Test path traversal operations."""
    
    def test_traverse_simple_path(self):
        """Test traversing a simple linear path."""
        graph = KnowledgeGraph()
        queries = GraphQueries(graph)
        
        goal = Goal(id="goal-1", name="Goal", statement="Test")
        req = Requirement(id="req-1", name="Requirement")
        cap = Capability(id="cap-1", name="Capability")
        
        graph.add_node(goal)
        graph.add_node(req)
        graph.add_node(cap)
        
        graph.add_edge(BaseEdge(edge_type="SATISFIED_BY", source_id="goal-1", target_id="req-1"))
        graph.add_edge(BaseEdge(edge_type="REALIZED_BY", source_id="req-1", target_id="cap-1"))
        
        paths = queries.traverse_path("goal-1", ["SATISFIED_BY", "REALIZED_BY"])
        
        assert len(paths) == 1
        assert len(paths[0]) == 3
        assert paths[0][0].id == "goal-1"
        assert paths[0][1].id == "req-1"
        assert paths[0][2].id == "cap-1"
    
    def test_traverse_branching_path(self):
        """Test traversing a path with branches."""
        graph = KnowledgeGraph()
        queries = GraphQueries(graph)
        
        goal = Goal(id="goal-1", name="Goal", statement="Test")
        req1 = Requirement(id="req-1", name="Requirement 1")
        req2 = Requirement(id="req-2", name="Requirement 2")
        cap1 = Capability(id="cap-1", name="Capability 1")
        cap2 = Capability(id="cap-2", name="Capability 2")
        
        graph.add_node(goal)
        graph.add_node(req1)
        graph.add_node(req2)
        graph.add_node(cap1)
        graph.add_node(cap2)
        
        # Goal -> 2 Requirements -> 2 Capabilities each
        graph.add_edge(BaseEdge(edge_type="SATISFIED_BY", source_id="goal-1", target_id="req-1"))
        graph.add_edge(BaseEdge(edge_type="SATISFIED_BY", source_id="goal-1", target_id="req-2"))
        graph.add_edge(BaseEdge(edge_type="REALIZED_BY", source_id="req-1", target_id="cap-1"))
        graph.add_edge(BaseEdge(edge_type="REALIZED_BY", source_id="req-2", target_id="cap-2"))
        
        paths = queries.traverse_path("goal-1", ["SATISFIED_BY", "REALIZED_BY"])
        
        assert len(paths) == 2
        assert all(len(path) == 3 for path in paths)
    
    def test_traverse_path_max_depth(self):
        """Test path traversal with max depth limit."""
        graph = KnowledgeGraph()
        queries = GraphQueries(graph)
        
        goal = Goal(id="goal-1", name="Goal", statement="Test")
        req = Requirement(id="req-1", name="Requirement")
        cap = Capability(id="cap-1", name="Capability")
        
        graph.add_node(goal)
        graph.add_node(req)
        graph.add_node(cap)
        
        graph.add_edge(BaseEdge(edge_type="SATISFIED_BY", source_id="goal-1", target_id="req-1"))
        graph.add_edge(BaseEdge(edge_type="REALIZED_BY", source_id="req-1", target_id="cap-1"))
        
        # Limit to depth 1
        paths = queries.traverse_path("goal-1", ["SATISFIED_BY", "REALIZED_BY"], max_depth=1)
        
        assert len(paths) == 1
        assert len(paths[0]) == 2  # Only goal -> req
    
    def test_find_reachable_nodes(self):
        """Test finding all reachable nodes from a starting point."""
        graph = KnowledgeGraph()
        queries = GraphQueries(graph)
        
        goal = Goal(id="goal-1", name="Goal", statement="Test")
        req = Requirement(id="req-1", name="Requirement")
        cap = Capability(id="cap-1", name="Capability")
        comp = Component(id="comp-1", name="Component")
        isolated = Goal(id="goal-2", name="Isolated", statement="Test")
        
        graph.add_node(goal)
        graph.add_node(req)
        graph.add_node(cap)
        graph.add_node(comp)
        graph.add_node(isolated)
        
        graph.add_edge(BaseEdge(edge_type="SATISFIED_BY", source_id="goal-1", target_id="req-1"))
        graph.add_edge(BaseEdge(edge_type="REALIZED_BY", source_id="req-1", target_id="cap-1"))
        graph.add_edge(BaseEdge(edge_type="REALIZED_BY", source_id="cap-1", target_id="comp-1"))
        
        reachable = queries.find_reachable_nodes("goal-1")
        
        assert len(reachable) == 4  # goal, req, cap, comp
        assert "goal-1" in reachable
        assert "req-1" in reachable
        assert "cap-1" in reachable
        assert "comp-1" in reachable
        assert "goal-2" not in reachable
    
    def test_find_reachable_nodes_filtered_by_edge_type(self):
        """Test finding reachable nodes following only specific edge types."""
        graph = KnowledgeGraph()
        queries = GraphQueries(graph)
        
        goal = Goal(id="goal-1", name="Goal", statement="Test")
        req = Requirement(id="req-1", name="Requirement")
        cap = Capability(id="cap-1", name="Capability")
        
        graph.add_node(goal)
        graph.add_node(req)
        graph.add_node(cap)
        
        graph.add_edge(BaseEdge(edge_type="SATISFIED_BY", source_id="goal-1", target_id="req-1"))
        graph.add_edge(BaseEdge(edge_type="REALIZED_BY", source_id="req-1", target_id="cap-1"))
        
        # Only follow SATISFIED_BY edges
        reachable = queries.find_reachable_nodes("goal-1", edge_types=["SATISFIED_BY"])
        
        assert len(reachable) == 2  # goal, req (not cap)
        assert "goal-1" in reachable
        assert "req-1" in reachable
        assert "cap-1" not in reachable


class TestCoverageAnalysis:
    """Test coverage analysis operations."""
    
    def test_get_coverage_ratio_full(self):
        """Test coverage ratio when all nodes have edges."""
        graph = KnowledgeGraph()
        queries = GraphQueries(graph)
        
        goal1 = Goal(id="goal-1", name="Goal 1", statement="Test")
        goal2 = Goal(id="goal-2", name="Goal 2", statement="Test")
        req1 = Requirement(id="req-1", name="Requirement 1")
        req2 = Requirement(id="req-2", name="Requirement 2")
        
        graph.add_node(goal1)
        graph.add_node(goal2)
        graph.add_node(req1)
        graph.add_node(req2)
        
        graph.add_edge(BaseEdge(edge_type="SATISFIED_BY", source_id="goal-1", target_id="req-1"))
        graph.add_edge(BaseEdge(edge_type="SATISFIED_BY", source_id="goal-2", target_id="req-2"))
        
        ratio = queries.get_coverage_ratio("goal", "SATISFIED_BY", direction="out")
        assert ratio == 1.0
    
    def test_get_coverage_ratio_partial(self):
        """Test coverage ratio when some nodes lack edges."""
        graph = KnowledgeGraph()
        queries = GraphQueries(graph)
        
        goal1 = Goal(id="goal-1", name="Goal 1", statement="Test")
        goal2 = Goal(id="goal-2", name="Goal 2", statement="Test")
        goal3 = Goal(id="goal-3", name="Goal 3", statement="Test")
        req = Requirement(id="req-1", name="Requirement")
        
        graph.add_node(goal1)
        graph.add_node(goal2)
        graph.add_node(goal3)
        graph.add_node(req)
        
        # Only goal-1 has edge
        graph.add_edge(BaseEdge(edge_type="SATISFIED_BY", source_id="goal-1", target_id="req-1"))
        
        ratio = queries.get_coverage_ratio("goal", "SATISFIED_BY", direction="out")
        assert abs(ratio - 0.333) < 0.01  # 1/3
    
    def test_get_coverage_ratio_empty(self):
        """Test coverage ratio when no nodes have edges."""
        graph = KnowledgeGraph()
        queries = GraphQueries(graph)
        
        goal1 = Goal(id="goal-1", name="Goal 1", statement="Test")
        goal2 = Goal(id="goal-2", name="Goal 2", statement="Test")
        
        graph.add_node(goal1)
        graph.add_node(goal2)
        
        ratio = queries.get_coverage_ratio("goal", "SATISFIED_BY", direction="out")
        assert ratio == 0.0
    
    def test_get_coverage_ratio_no_nodes(self):
        """Test coverage ratio when no nodes of type exist."""
        graph = KnowledgeGraph()
        queries = GraphQueries(graph)
        
        ratio = queries.get_coverage_ratio("goal", "SATISFIED_BY", direction="out")
        assert ratio == 0.0
