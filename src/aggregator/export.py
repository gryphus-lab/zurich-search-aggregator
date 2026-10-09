"""
Result serialization helpers shared by the CLI and the API.

CSV is the default output format. The internal ``raw_data`` debug blob is
excluded from CSV (it is retained in the JSON output).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import List

from .models import ApartmentListing

# Human-friendly CSV column order. The internal ``raw_data`` field is omitted.
CSV_COLUMNS: List[str] = [
    "source",
    "title",
    "price_chf",
    "rooms",
    "size_m2",
    "neighborhood",
    "address",
    "available_from",
    "furnished",
    "link",
    "id",
    "description_snippet",
]


def write_json(listings: List[ApartmentListing], path: Path) -> None:
    """Write listings as a JSON array (full fidelity, including raw_data)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = [item.model_dump(mode="json") for item in listings]
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False, default=str)


def write_csv(listings: List[ApartmentListing], path: Path) -> None:
    """Write listings as CSV with the shared, human-friendly column order."""
    import pandas as pd

    path.parent.mkdir(parents=True, exist_ok=True)
    df = pd.DataFrame(
        [item.model_dump(mode="json", exclude={"raw_data"}) for item in listings]
    )
    # Reindex to the preferred order; tolerate an empty result set.
    if not df.empty:
        df = df.reindex(columns=CSV_COLUMNS)
    else:
        df = pd.DataFrame(columns=CSV_COLUMNS)
    df.to_csv(path, index=False)
