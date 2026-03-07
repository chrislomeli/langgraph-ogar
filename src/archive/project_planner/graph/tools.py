"""
DEPRECATED — Tools have moved to src/tools/project_tools.py.

This file re-exports build_project_tools as build_tools for backward compatibility.
Update your imports to: from tools.project_tools import build_project_tools
"""

from tools.project_tools import build_project_tools as build_tools

__all__ = ["build_tools"]
