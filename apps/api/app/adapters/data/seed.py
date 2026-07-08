"""Deterministic synthetic seed for the fixture DataSource — KRW-ballpark data.

Rows are generated (seeded RNG, no clock) to match the placeholder registry's schema and
roll up to the demo numbers: ~86k leads, ~$37M spend, ROAS ~3.4x, spread across channels,
Texas-heavy metros, and a rolling ~year so grain/range/period-over-period all have shape.

This is coupled to the *placeholder* registry (analytics.v_leads + analytics.v_geo). When
the real KRW schema lands (C3), the registry and this seed move together.
"""

import random
from datetime import date, timedelta

# Column layout per table (typeless — SQLite stores what we insert), matching the registry.
SCHEMA: dict[str, list[str]] = {
    "v_leads": ["lead_id", "channel", "metro", "created_at", "spend", "revenue"],
    "v_geo": ["lead_id", "state"],
}

_CHANNELS = ["Facebook", "Google", "Referral", "Linear TV", "Website"]
_CHANNEL_WEIGHTS = [34, 28, 14, 9, 15]
_METROS = [
    ("Houston", "TX"),
    ("Dallas", "TX"),
    ("Austin", "TX"),
    ("San Antonio", "TX"),
    ("El Paso", "TX"),
    ("Phoenix", "AZ"),
    ("Los Angeles", "CA"),
]
# ~1-year window ending recently, fixed so the seed stays deterministic (no clock read).
_WINDOW_START = date(2025, 7, 1)
_WINDOW_DAYS = 365


def build_rows(leads: int, seed: int) -> dict[str, list[dict[str, object]]]:
    """Generate the fixture's rows: one lead per id, one geo row per lead (1:1)."""

    rng = random.Random(seed)
    lead_rows: list[dict[str, object]] = []
    geo_rows: list[dict[str, object]] = []
    for lead_id in range(leads):
        metro, state = rng.choice(_METROS)
        created = _WINDOW_START + timedelta(days=rng.randint(0, _WINDOW_DAYS))
        spend = round(rng.uniform(50.0, 810.0), 2)  # avg ~$430 → ~$37M over ~86k
        revenue = round(spend * rng.uniform(1.4, 5.4), 2)  # ROAS ~3.4x on average
        lead_rows.append(
            {
                "lead_id": lead_id,
                "channel": rng.choices(_CHANNELS, weights=_CHANNEL_WEIGHTS)[0],
                "metro": metro,
                "created_at": created.isoformat(),
                "spend": spend,
                "revenue": revenue,
            }
        )
        geo_rows.append({"lead_id": lead_id, "state": state})
    return {"v_leads": lead_rows, "v_geo": geo_rows}
