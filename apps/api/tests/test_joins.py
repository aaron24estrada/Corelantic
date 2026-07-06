import pytest

from app.semantic.errors import NoJoinPathError
from app.semantic.joins import JoinStep, find_join_path
from app.semantic.models import Cardinality, Entity, JoinEdge, SemanticRegistry


def _registry() -> SemanticRegistry:
    # leads → geo, geo → dim_date; stages is unconnected.
    return SemanticRegistry(
        entities={
            "leads": Entity(
                name="leads",
                label="Leads",
                source="v_leads",
                joins=[JoinEdge(to="geo", left="lead_id", right="lead_id")],
            ),
            "geo": Entity(
                name="geo",
                label="Geo",
                source="v_geo",
                joins=[JoinEdge(to="dim_date", left="date_id", right="id")],
            ),
            "dim_date": Entity(name="dim_date", label="Date", source="v_dim_date"),
            "stages": Entity(name="stages", label="Stages", source="v_stages"),
        }
    )


def test_same_entity_needs_no_join() -> None:
    assert find_join_path("leads", "leads", _registry()) == []


def test_single_hop_path() -> None:
    assert find_join_path("leads", "geo", _registry()) == [
        JoinStep("leads", "lead_id", "geo", "lead_id")
    ]


def test_multi_hop_path_is_ordered_from_the_base() -> None:
    assert find_join_path("leads", "dim_date", _registry()) == [
        JoinStep("leads", "lead_id", "geo", "lead_id"),
        JoinStep("geo", "date_id", "dim_date", "id"),
    ]


def test_edges_traverse_in_reverse() -> None:
    # geo declared no edge to leads, but leads → geo is usable from geo's side too.
    assert find_join_path("geo", "leads", _registry()) == [
        JoinStep("geo", "lead_id", "leads", "lead_id")
    ]


def test_no_path_raises() -> None:
    with pytest.raises(NoJoinPathError):
        find_join_path("leads", "stages", _registry())


def test_many_to_one_fans_out_only_backward() -> None:
    # leads → geo is the default many-to-one (fact → dimension).
    registry = _registry()
    assert find_join_path("leads", "geo", registry)[0].fans_out is False  # joining the dim
    assert find_join_path("geo", "leads", registry)[0].fans_out is True  # joining the fact


def test_one_to_many_fans_out_forward() -> None:
    registry = SemanticRegistry(
        entities={
            "leads": Entity(
                name="leads",
                label="Leads",
                source="v_leads",
                joins=[
                    JoinEdge(
                        to="events",
                        left="lead_id",
                        right="lead_id",
                        cardinality=Cardinality.ONE_TO_MANY,
                    )
                ],
            ),
            "events": Entity(name="events", label="Events", source="v_events"),
        }
    )
    assert find_join_path("leads", "events", registry)[0].fans_out is True
    assert find_join_path("events", "leads", registry)[0].fans_out is False


def test_prefers_a_fan_out_free_path_over_a_shorter_fan_out_one() -> None:
    # A → B is a direct one-to-many (fans out); A → C → B is all many-to-one (safe).
    registry = SemanticRegistry(
        entities={
            "a": Entity(
                name="a",
                label="A",
                source="va",
                joins=[
                    JoinEdge(to="b", left="k", right="k", cardinality=Cardinality.ONE_TO_MANY),
                    JoinEdge(to="c", left="ck", right="ck"),
                ],
            ),
            "c": Entity(
                name="c",
                label="C",
                source="vc",
                joins=[JoinEdge(to="b", left="bk", right="bk")],
            ),
            "b": Entity(name="b", label="B", source="vb"),
        }
    )
    path = find_join_path("a", "b", registry)
    assert [step.to_entity for step in path] == ["c", "b"]  # the safe 2-hop route
    assert not any(step.fans_out for step in path)
