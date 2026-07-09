"""Deterministic synthetic seed for the fixture DataSource — KRW-ballpark data.

Rows are generated (seeded RNG, no clock) to mirror gold_tspot's shape and the Executive
Summary numbers: ~86k leads over 2023-2026, channel mix and Texas-heavy geography matching
the real distribution, and ~38% of leads with no geo row (as in the source, so grouping by
state reproduces the dashboard's "(Blank)" bucket and exercises the outer join).

The fixture and the real warehouse share one registry, so this seeds the same tables the
Azure adapter reads (gold_tspot.cases, gold_tspot.geo).
"""

import random
from datetime import date, timedelta

# Column layout per table (typeless — SQLite stores what we insert), matching the registry.
SCHEMA: dict[str, list[str]] = {
    "cases": ["LeadId", "CreateDate", "source_category", "Status"],
    "geo": ["LeadId", "State"],
}

# Channel mix, weighted to the live source_category counts.
_CHANNELS = [
    "CTV",
    "Linear TV",
    "Phone/SMS",
    "Facebook",
    "Referral",
    "Unknown",
    "Other Social Media",
    "Website/Email",
    "Other",
]
_CHANNEL_WEIGHTS = [20411, 18378, 16239, 15391, 11191, 2631, 1180, 1079, 473]

# A representative slice of the 87 real statuses, weighted roughly to the source.
_STATUSES = [
    "Asbestos - DNQ",
    "Close File",
    "Asbestos - Bank Complete",
    "Closed",
    "NEW INQUIRY",
    "Asbestos - M4",
]
_STATUS_WEIGHTS = [24074, 15806, 11778, 10259, 6262, 4369]

# Geography, weighted to the live State counts (among leads that have geo).
_STATES = ["TX", "LA", "AL", "MS", "MI", "FL", "CA", "GA", "OH", "TN"]
_STATE_WEIGHTS = [41943, 24459, 8561, 8165, 3190, 1498, 892, 784, 618, 536]
# Share of leads that carry a geo row (the rest are the dashboard's "(Blank)" 38%).
_GEO_COVERAGE = 0.616

# Fixed 2023-2026 window (matches the real CreateDate span), so the seed stays clockless.
_WINDOW_START = date(2023, 1, 1)
_WINDOW_DAYS = 1285


def build_rows(leads: int, seed: int) -> dict[str, list[dict[str, object]]]:
    """Generate the fixture's rows: one case per lead, a geo row for ~62% of them."""

    rng = random.Random(seed)
    case_rows: list[dict[str, object]] = []
    geo_rows: list[dict[str, object]] = []
    for lead_id in range(leads):
        created = _WINDOW_START + timedelta(days=rng.randint(0, _WINDOW_DAYS))
        case_rows.append(
            {
                "LeadId": lead_id,
                "CreateDate": created.isoformat(),
                "source_category": rng.choices(_CHANNELS, weights=_CHANNEL_WEIGHTS)[0],
                "Status": rng.choices(_STATUSES, weights=_STATUS_WEIGHTS)[0],
            }
        )
        if rng.random() < _GEO_COVERAGE:
            state = rng.choices(_STATES, weights=_STATE_WEIGHTS)[0]
            geo_rows.append({"LeadId": lead_id, "State": state})
    return {"cases": case_rows, "geo": geo_rows}
