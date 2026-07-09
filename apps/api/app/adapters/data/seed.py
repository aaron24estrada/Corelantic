"""Deterministic synthetic seed for the fixture DataSource — KRW-ballpark data.

Rows are generated (seeded RNG, no clock) to mirror gold_tspot's shape and the Executive
Summary numbers: ~86k leads over 2023-2026, channel mix and Texas-heavy geography matching
the real distribution, and ~38% of leads with no geo row (as in the source, so grouping by
state reproduces the dashboard's "(Blank)" bucket and exercises the outer join). The funnel,
call dispositions, and agent conversion follow the shares measured against the live tables.

The fixture and the real warehouse share one registry, so this seeds the same tables the
Azure adapter reads: cases, geo, stages, zoom_calls, and agent_stats.
"""

import random
from datetime import date, timedelta

# Column layout per table (typeless — SQLite stores what we insert), matching the registry.
SCHEMA: dict[str, list[str]] = {
    "cases": ["LeadId", "CreateDate", "source_category", "Status"],
    "geo": ["LeadId", "State"],
    "stages": ["LeadId", "StageName", "StageOrder", "milestone_complete", "DateCompleted"],
    "zoom_calls": [
        "call_id",
        "call_date",
        "direction",
        "call_result",
        "duration",
        "answer_time",
        "wait_time_sec",
        "is_queue_routed",
        "spam",
        "region",
        "agent_name",
        "site_name",
        "LeadId",
    ],
    "agent_stats": ["week_start", "agent_name", "region", "leads_contacted", "leads_converted"],
}

# The intake funnel and each stage's cumulative reach (share of leads getting that far),
# from the live source. Reach is monotonic, so a lead reaches a prefix of the stages.
_FUNNEL = [
    ("Lead", 1.000),
    ("Voucher (Initial Intake)", 0.242),
    ("X-Ray Received", 0.184),
    ("X-Ray to B-Read", 0.171),
    ("B-Read Results", 0.168),
    ("Sched. for Clinic", 0.160),
    ("Bank Incomplete", 0.152),
    ("Bank Complete", 0.147),
]

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

# Telephony covers a recent window only, not the lead tables' three years.
_CALL_WINDOW_START = date(2026, 1, 1)
_CALL_WINDOW_DAYS = 189
_CALLS_PER_LEAD = 92_741 / 86_973

# Call dispositions, and the share of each that was actually picked up (has an answer_time).
# A hang_up is often an answered call the caller then dropped, which is why answer_time —
# not call_result — defines "answered".
_CALL_RESULTS = [
    ("connected", 42_161, 1.000),
    ("answered", 28_972, 1.000),
    ("hang_up", 10_239, 0.346),
    ("no_answer", 4_377, 0.000),
    ("abandoned", 3_985, 0.074),
    ("voicemail", 2_981, 0.000),
    ("blocked", 26, 1.000),
]
_CALL_REGIONS = ["SAN", "HOU", "REMOTE", "ABL", "AUS", "ODS", "NOLA", "BMT", "BRM"]
_CALL_REGION_WEIGHTS = [39_273, 37_099, 15_825, 190, 173, 94, 35, 34, 18]
_OUTBOUND_SHARE = 52_400 / 92_741
_QUEUE_ROUTED_SHARE = 45_772 / 92_741
_SPAM_SHARE = 24 / 92_741
_LINKED_SHARE = 47_150 / 92_741
_DUPLICATE_CALL_ID_SHARE = 1 - 82_868 / 92_741  # rows sharing a call_id (call legs)
_MEAN_DURATION_SECONDS = 113.7
_MAX_DURATION_SECONDS = 11_910
_MEAN_WAIT_SECONDS = 7.7
_MAX_WAIT_SECONDS = 150

_AGENTS = 87
_AGENT_STAT_ROWS = 391
_AGENT_WEEK_START = date(2025, 12, 29)
_AGENT_WEEKS = 28
_MEAN_CONTACTED = 13_378 / 391
_CONVERSION_RATE = 594 / 13_378  # pooled 4.44%


def build_rows(leads: int, seed: int) -> dict[str, list[dict[str, object]]]:
    """One case per lead, a geo row for ~62% of them, and the stage rows each lead reached."""

    rng = random.Random(seed)
    case_rows: list[dict[str, object]] = []
    geo_rows: list[dict[str, object]] = []
    stage_rows: list[dict[str, object]] = []
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

        # One draw decides how far the lead got: it reaches every stage whose cumulative
        # reach still exceeds the draw, which is a prefix since reach only decreases.
        progress = rng.random()
        for order, (stage, reach) in enumerate(_FUNNEL):
            if reach <= progress:
                break
            stage_rows.append(
                {
                    "LeadId": lead_id,
                    "StageName": stage,
                    "StageOrder": order,
                    "milestone_complete": 1,
                    "DateCompleted": (created + timedelta(days=order * 7)).isoformat(),
                }
            )
    return {
        "cases": case_rows,
        "geo": geo_rows,
        "stages": stage_rows,
        "zoom_calls": _build_calls(leads, rng),
        "agent_stats": _build_agent_stats(rng),
    }


def _agent_name(index: int) -> str:
    return f"Agent {index:03d}"


def _bounded_exponential(rng: random.Random, mean: float, cap: int) -> int:
    return min(int(rng.expovariate(1 / mean)), cap)


def _build_calls(leads: int, rng: random.Random) -> list[dict[str, object]]:
    results = [name for name, _, _ in _CALL_RESULTS]
    weights = [weight for _, weight, _ in _CALL_RESULTS]
    answered_share = {name: share for name, _, share in _CALL_RESULTS}

    rows: list[dict[str, object]] = []
    previous_call_id = "c0"
    for index in range(round(leads * _CALLS_PER_LEAD)):
        # Some rows share a call_id: one call can have several legs.
        reuse = index > 0 and rng.random() < _DUPLICATE_CALL_ID_SHARE
        call_id = previous_call_id if reuse else f"c{index}"
        previous_call_id = call_id

        called = _CALL_WINDOW_START + timedelta(days=rng.randint(0, _CALL_WINDOW_DAYS))
        result = rng.choices(results, weights=weights)[0]
        answered = rng.random() < answered_share[result]
        duration = _bounded_exponential(rng, _MEAN_DURATION_SECONDS, _MAX_DURATION_SECONDS)
        rows.append(
            {
                "call_id": call_id,
                "call_date": called.isoformat(),
                "direction": "outbound" if rng.random() < _OUTBOUND_SHARE else "inbound",
                "call_result": result,
                "duration": duration,
                "answer_time": f"{called.isoformat()}T12:00:00" if answered else None,
                "wait_time_sec": _bounded_exponential(rng, _MEAN_WAIT_SECONDS, _MAX_WAIT_SECONDS),
                "is_queue_routed": int(rng.random() < _QUEUE_ROUTED_SHARE),
                "spam": "maybe_spam" if rng.random() < _SPAM_SHARE else None,
                "region": rng.choices(_CALL_REGIONS, weights=_CALL_REGION_WEIGHTS)[0],
                "agent_name": _agent_name(rng.randrange(_AGENTS)),
                "site_name": rng.choice(["San Antonio", "Houston", "Remote"]),
                "LeadId": rng.randrange(leads) if rng.random() < _LINKED_SHARE else None,
            }
        )
    return rows


def _build_agent_stats(rng: random.Random) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for index in range(_AGENT_STAT_ROWS):
        week = _AGENT_WEEK_START + timedelta(weeks=rng.randrange(_AGENT_WEEKS))
        contacted = max(1, int(rng.expovariate(1 / _MEAN_CONTACTED)))
        # Draw conversions from the pooled rate, so sum(converted)/sum(contacted) holds.
        converted = sum(1 for _ in range(contacted) if rng.random() < _CONVERSION_RATE)
        rows.append(
            {
                "week_start": week.isoformat(),
                "agent_name": _agent_name(index % _AGENTS),
                "region": rng.choices(_CALL_REGIONS, weights=_CALL_REGION_WEIGHTS)[0],
                "leads_contacted": contacted,
                "leads_converted": converted,
            }
        )
    return rows
