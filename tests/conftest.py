"""
Pytest configuration and shared fixtures for OGAR.
"""

import pytest

from ogar.domain.models.project import Project, Goal, Requirement


@pytest.fixture
def sample_project() -> Project:
    """A minimal project with 2 goals and 1 requirement."""
    return Project(
        pid="test_proj",
        title="Test Project",
        goals={
            "g_1": Goal(gid="g_1", statement="First goal", success_metrics=["m1"]),
            "g_2": Goal(gid="g_2", statement="Second goal", success_metrics=["m2"]),
        },
        requirements={
            "r_1": Requirement(
                rid="r_1",
                type="functional",
                statement="First requirement",
                source_goal_ids=["g_1"],
            ),
        },
    )
