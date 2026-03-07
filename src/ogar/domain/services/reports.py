from __future__ import annotations

from datetime import datetime, timedelta
from typing import List, Optional

from ogar.domain.models.project import Project, UncertaintyItem


def report_blocking_uncertainties(project: Project) -> List[UncertaintyItem]:
    out = [
        u for u in project.uncertainties.values()
        if u.status != "resolved" and u.blocks_progress
    ]
    return _sort_uncertainties(out)


def report_orphan_uncertainties(project: Project) -> List[UncertaintyItem]:
    out = [
        u for u in project.uncertainties.values()
        if u.status != "resolved" and len(u.links) == 0
    ]
    return _sort_uncertainties(out)


def report_stale_uncertainties(
    project: Project,
    *,
    stale_after_days: int = 14,
    now: Optional[datetime] = None,
) -> List[UncertaintyItem]:
    now = now or datetime.utcnow()
    cutoff = now - timedelta(days=stale_after_days)

    out: List[UncertaintyItem] = []
    for u in project.uncertainties.values():
        if u.status == "resolved":
            continue
        last = u.last_reviewed_at or u.created_at
        if last < cutoff:
            out.append(u)

    return _sort_uncertainties(out)


def _sort_uncertainties(items: List[UncertaintyItem]) -> List[UncertaintyItem]:
    impact_rank = {"high": 0, "medium": 1, "low": 2}
    return sorted(items, key=lambda u: (impact_rank[u.impact], u.last_reviewed_at or u.created_at))