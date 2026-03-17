"""
Tests for conversation_engine Pydantic models.

Validates that models can be instantiated and serialized correctly.
"""
import pytest
from pydantic import ValidationError

from conversation_engine.models import (
    Goal,
    Requirement,
    Capability,
    Component,
    IntegrityRule,
    GraphQueryPattern,
    Assessment,
    GoalRequirementTrace,
)
from conversation_engine.examples.ontology_data import (
    get_goals,
    get_requirements,
    get_capabilities,
    get_components,
    get_sample_integrity_rules,
    get_sample_query_patterns,
    get_goal_requirement_traces,
)


class TestNodeModels:
    """Test node type models."""
    
    def test_goal_creation(self):
        """Test Goal model instantiation."""
        goal = Goal(
            id="goal-test",
            name="Test Goal",
            statement="This is a test goal statement."
        )
        assert goal.id == "goal-test"
        assert goal.name == "Test Goal"
        assert goal.statement == "This is a test goal statement."
    
    def test_goal_serialization(self):
        """Test Goal model serialization."""
        goal = Goal(
            id="goal-test",
            name="Test Goal",
            statement="This is a test goal statement."
        )
        data = goal.model_dump()
        assert data["id"] == "goal-test"
        assert data["name"] == "Test Goal"
        
        goal_from_dict = Goal(**data)
        assert goal_from_dict.id == goal.id
    
    def test_requirement_creation(self):
        """Test Requirement model instantiation."""
        req = Requirement(
            id="REQ-001",
            name="Test Requirement",
            requirement_type="functional",
            description="A test requirement"
        )
        assert req.id == "REQ-001"
        assert req.requirement_type == "functional"
    
    def test_component_with_no_dependencies(self):
        """Test Component with explicit no dependencies flag."""
        component = Component(
            id="component-test",
            name="Test Component",
            has_no_dependencies=True
        )
        assert component.has_no_dependencies is True


class TestTraceabilityModels:
    """Test traceability models."""
    
    def test_goal_requirement_trace(self):
        """Test GoalRequirementTrace model."""
        trace = GoalRequirementTrace(
            goal_id="goal-1",
            requirement_ids=["REQ-001", "REQ-002"]
        )
        assert trace.goal_id == "goal-1"
        assert len(trace.requirement_ids) == 2
        assert "REQ-001" in trace.requirement_ids
    
    def test_empty_trace(self):
        """Test trace with no linked items."""
        trace = GoalRequirementTrace(
            goal_id="goal-orphan",
            requirement_ids=[]
        )
        assert len(trace.requirement_ids) == 0


class TestIntegrityRules:
    """Test integrity rule models."""
    
    def test_integrity_rule_creation(self):
        """Test IntegrityRule model instantiation."""
        rule = IntegrityRule(
            id="rule-test",
            name="Test Rule",
            description="A test rule",
            applies_to_node_type="goal",
            rule_type="minimum_outgoing_edge_count",
            edge_type="SATISFIED_BY",
            target_node_types=["requirement"],
            minimum_count=1,
            severity="high",
            failure_message_template="Goal '{subject_name}' has no requirements."
        )
        assert rule.id == "rule-test"
        assert rule.severity == "high"
        assert rule.minimum_count == 1
    
    def test_integrity_rule_immutable(self):
        """Test that IntegrityRule is frozen."""
        rule = IntegrityRule(
            id="rule-test",
            name="Test Rule",
            description="A test rule",
            applies_to_node_type="goal",
            rule_type="minimum_outgoing_edge_count",
            edge_type="SATISFIED_BY",
            target_node_types=["requirement"],
            minimum_count=1,
            severity="high",
            failure_message_template="Test"
        )
        with pytest.raises(ValidationError):
            rule.severity = "low"


class TestQueryPatterns:
    """Test query pattern models."""
    
    def test_query_pattern_with_checks(self):
        """Test GraphQueryPattern with edge checks."""
        patterns = get_sample_query_patterns()
        gap_query = patterns[0]
        
        assert gap_query.id == "query-missing-goal-coverage"
        assert gap_query.query_intent == "gap_detection"
        assert gap_query.checks is not None
        assert len(gap_query.checks) == 1
        assert gap_query.checks[0].edge_type == "SATISFIED_BY"
    
    def test_query_pattern_with_path(self):
        """Test GraphQueryPattern with path pattern."""
        patterns = get_sample_query_patterns()
        lineage_query = patterns[2]
        
        assert lineage_query.id == "query-goal-to-component-lineage"
        assert lineage_query.query_intent == "lineage_trace"
        assert lineage_query.path_pattern is not None
        assert len(lineage_query.path_pattern) == 3


class TestAssessmentModels:
    """Test assessment output models."""
    
    def test_assessment_creation(self):
        """Test Assessment model instantiation."""
        assessment = Assessment(
            id="assessment-001",
            assessment_type="missing_goal_coverage",
            severity="high",
            subject_ids=["goal-1"],
            finding="Goal has no linked requirements.",
            evidence=["No SATISFIED_BY edges found"],
            related_rule_ids=["rule-goal-must-have-requirement"],
            suggested_actions=["Add requirements to satisfy this goal"],
            confidence="high"
        )
        assert assessment.id == "assessment-001"
        assert assessment.severity == "high"
        assert len(assessment.evidence) == 1
        assert len(assessment.suggested_actions) == 1


class TestExampleData:
    """Test that example data from ontology loads correctly."""
    
    def test_load_goals(self):
        """Test loading goals from example data."""
        goals = get_goals()
        assert len(goals) == 5
        assert all(isinstance(g, Goal) for g in goals)
        assert goals[0].id == "goal-structured-convergence"
    
    def test_load_requirements(self):
        """Test loading requirements from example data."""
        requirements = get_requirements()
        assert len(requirements) == 20
        assert all(isinstance(r, Requirement) for r in requirements)
    
    def test_load_capabilities(self):
        """Test loading capabilities from example data."""
        capabilities = get_capabilities()
        assert len(capabilities) == 7
        assert all(isinstance(c, Capability) for c in capabilities)
    
    def test_load_components(self):
        """Test loading components from example data."""
        components = get_components()
        assert len(components) == 7
        assert all(isinstance(c, Component) for c in components)
    
    def test_load_traceability(self):
        """Test loading traceability data."""
        traces = get_goal_requirement_traces()
        assert len(traces) == 5
        assert all(isinstance(t, GoalRequirementTrace) for t in traces)
        
        first_trace = traces[0]
        assert first_trace.goal_id == "goal-structured-convergence"
        assert len(first_trace.requirement_ids) == 4
    
    def test_load_integrity_rules(self):
        """Test loading integrity rules."""
        rules = get_sample_integrity_rules()
        assert len(rules) == 3
        assert all(isinstance(r, IntegrityRule) for r in rules)
    
    def test_load_query_patterns(self):
        """Test loading query patterns."""
        patterns = get_sample_query_patterns()
        assert len(patterns) == 3
        assert all(isinstance(p, GraphQueryPattern) for p in patterns)
