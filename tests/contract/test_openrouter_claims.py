"""Parsing the claim extractor's answers. Made-up statements (ADR-005)."""

import json

import pytest

from lektyra.adapters.llm.openrouter_claims import SCHEMA, parse
from lektyra.domain.claims import Add, Amend, Link, Withdraw


def completion(actions: list[dict[str, object]], cost: float = 0.0012) -> str:
    content = json.dumps({"actions": actions}, ensure_ascii=False)
    return json.dumps({"choices": [{"message": {"content": content}}], "usage": {"cost": cost}})


def item(**fields: object) -> dict[str, object]:
    base: dict[str, object] = {k: None for k in SCHEMA["properties"]["actions"]["items"]["properties"]}
    base.update(fields)
    return base


def test_every_action_kind_is_parsed() -> None:
    body = completion([
        item(op="add", speaker="S1", at="20:34", quote="dali sme 200 miliónov", lekton="Vláda dala 200 mil. €.",
             kind="money", entities=["Vláda SR"], numbers=["200 mil. €"], sources=["budget"], worth=0.9),
        item(op="amend", id="c1", lekton="Vláda dala v roku 2024 200 mil. €."),
        item(op="withdraw", id="c2", reason="opravil sa"),
        item(op="link", id="c3", relation="contradicts", other="c1"),
    ])  # fmt: skip
    parsed = parse(body, minute_start_ms=1_200_000)
    kinds = [type(a) for a in parsed.actions]
    assert kinds == [Add, Amend, Withdraw, Link]
    first = parsed.actions[0]
    assert isinstance(first, Add) and first.at_ms == 1_234_000 and first.sources == ("budget",)
    assert parsed.cost_usd == pytest.approx(0.0012)
    assert parsed.problems == []


def test_an_incomplete_action_is_reported_not_guessed() -> None:
    parsed = parse(completion([item(op="add", speaker="S1"), item(op="link", id="c1")]), 0)
    assert parsed.actions == []
    assert len(parsed.problems) == 2


def test_an_error_body_raises() -> None:
    with pytest.raises(ValueError, match="rate"):
        parse(json.dumps({"error": {"message": "rate limited"}}), 0)


def test_the_schema_is_strict() -> None:
    items = SCHEMA["properties"]["actions"]["items"]
    assert items["additionalProperties"] is False
    assert set(items["required"]) == set(items["properties"])
