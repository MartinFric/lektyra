"""The claim ledger's state machine (spike-plan §8). Made-up statements, no broadcast text (ADR-005)."""

from lektyra.domain.align import Utterance
from lektyra.domain.claims import Add, Amend, Ledger, Link, Withdraw, ledger_digest, minute_window, step


def add(lekton: str, speaker: str = "S1", at_ms: int = 0) -> Add:
    return Add(speaker, at_ms, lekton, lekton, "money", ("Ministerstvo X",), ("200 mil. €",), ("crz",), 0.8)


def test_adds_get_stable_ids_in_order() -> None:
    ledger = step(Ledger(), 1, [add("a"), add("b")])
    ledger = step(ledger, 2, [add("c")])
    assert [c.id for c in ledger.claims] == ["c1", "c2", "c3"]
    assert ledger.next_id == 4 and ledger.minute == 2


def test_a_claim_cut_at_the_minute_is_amended_not_added_twice() -> None:
    ledger = step(Ledger(), 1, [add("Ministerstvo zaplatilo")])
    ledger = step(ledger, 2, [Amend("c1", None, "Ministerstvo zaplatilo firme Y 200 mil. € v roku 2024", None, None)])
    assert len(ledger.claims) == 1
    assert ledger.claims[0].lekton.endswith("2024")
    assert ledger.claims[0].history == ("m1 add", "m2 amend")


def test_a_withdrawn_claim_stays_with_its_reason() -> None:
    ledger = step(step(Ledger(), 1, [add("x")]), 3, [Withdraw("c1", "speaker corrected the year")])
    assert ledger.claims[0].status == "withdrawn"
    assert "corrected" in ledger.claims[0].history[-1]
    assert "WITHDRAWN" in ledger_digest(ledger)


def test_links_only_between_existing_claims() -> None:
    ledger = step(Ledger(), 1, [add("x"), add("y", speaker="S2")])
    ledger = step(
        ledger, 2, [Link("c2", "contradicts", "c1"), Link("c2", "supports", "c9"), Amend("c7", "q", None, None, None)]
    )
    assert ledger.claims[1].links == (("contradicts", "c1"),)
    assert len(ledger.rejected) == 2  # an unknown id is recorded, never guessed at


def test_worth_is_clamped() -> None:
    a = Add("S1", 0, "q", "l", "number", (), (), (), 1.7)
    assert step(Ledger(), 1, [a]).claims[0].worth == 1.0


def test_the_window_is_two_minutes_of_context_and_the_new_minute() -> None:
    items = [Utterance(t * 30_000, t * 30_000 + 1000, "S1", f"veta {t}") for t in range(8)]  # every 30 s
    context, new = minute_window(items, minute=4)  # new = 3:00–4:00, context = 1:00–3:00
    assert new.splitlines() == ["[03:00] S1: veta 6", "[03:30] S1: veta 7"]
    assert context.splitlines()[0] == "[01:00] S1: veta 2"
    assert len(context.splitlines()) == 4
