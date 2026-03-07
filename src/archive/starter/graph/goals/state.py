"""
MusicGraphState — the state that flows through the entire graph.

M3 adds:
- plan field for the plan review node
- approved field for the human decision
"""

from __future__ import annotations

from typing import TypedDict, Optional

from enum import Enum

class IntentType(Enum):
    CREATE_NEW_PROJECT_GOALS = 1



class MusicGraphState(TypedDict, total=False):
    """State that flows through the graph. M3 extends this with plan/approved fields."""
    
    # M1 fields
    user_message: str
    intent_type: IntentType
    response: str
    
    # M3 fields
    plan: Optional[dict]       # The plan to review
    approved: Optional[bool]   # Human's decision (set via Command resume)

