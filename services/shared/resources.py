"""Shared helpers for picking a 'primary' resource on a CKAN dataset.

The agent + scanner + builder all want to anchor on the same resource for
a given dataset (the one most likely to be the actual data file). Keeping
the priority order in one place avoids drift.
"""
from __future__ import annotations

from typing import Any, Optional, Sequence

PRIMARY_FORMAT_PRIORITY: tuple[str, ...] = (
    "CSV", "GEOJSON", "JSON", "XLSX", "XML",
)


def _accessor(item: Any, key: str) -> Any:
    """Read `key` from either a dict or a pydantic/dataclass object."""
    if isinstance(item, dict):
        return item.get(key)
    return getattr(item, key, None)


def pick_primary_resource_id(resources: Sequence[Any]) -> Optional[str]:
    """Return the id of the most agent-friendly resource on a dataset.

    Walks `PRIMARY_FORMAT_PRIORITY` in order; first hit wins. Falls back
    to the first resource. Returns `None` if `resources` is empty.
    Accepts dicts or `.format`/`.id`-bearing objects.
    """
    for fmt in PRIMARY_FORMAT_PRIORITY:
        for r in resources:
            if (_accessor(r, "format") or "").upper() == fmt:
                return _accessor(r, "id")
    if not resources:
        return None
    return _accessor(resources[0], "id")
