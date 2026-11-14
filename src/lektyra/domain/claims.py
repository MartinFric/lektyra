"""The claim ledger: the lekton, minute by minute (spike-plan §8). Pure: the extractor is an adapter.

Every minute an extractor reads the new minute plus the two before it (context, so a claim cut at the boundary is
completed rather than extracted twice) and the ledger so far, and answers with actions:
- ADD: a new checkable claim;
- AMEND: a claim the new minute completed or corrected;
- WITHDRAW: the speaker took it back;
- LINK: a claim supports or contradicts another.

`step` applies them. It is the whole state machine, and replay = live: the same answers give the same ledger. A
claim belongs to a speaker label of the event (S1…N, "?"), never a guessed person (ADR-004); names come later and
attach to every claim of that label at once.
"""

from collections.abc import Sequence
from dataclasses import dataclass, field, replace
from typing import Final, Literal

from lektyra.domain.align import Utterance
from lektyra.domain.timefmt import clock

ClaimKind = Literal["number", "money", "contract", "company", "vote", "law", "date", "quote", "promise", "other"]
Source = Literal["crz", "ministry_invoices", "nrsr", "finstat", "budget", "statistics", "eu_funds", "media", "other"]
Relation = Literal["supports", "contradicts", "repeats"]
ClaimStatus = Literal["open", "withdrawn"]

MINUTE_MS: Final = 60_000
CONTEXT_MINUTES: Final = 2


@dataclass(frozen=True)
class Claim:
    id: str
    speaker: str
    at_ms: int
    quote: str  # as said, shortened
    lekton: str  # the checkable content in one sentence: who, what, how much, when
    kind: ClaimKind
    entities: tuple[str, ...]
    numbers: tuple[str, ...]
    sources: tuple[Source, ...]  # where it can be checked
    worth: float  # 0..1: checkable × weight (magnitude, topic, speaker) × novelty
    status: ClaimStatus = "open"
    links: tuple[tuple[Relation, str], ...] = ()
    history: tuple[str, ...] = ()  # "m21 add", "m22 amend", …


@dataclass(frozen=True)
class Add:
    speaker: str
    at_ms: int
    quote: str
    lekton: str
    kind: ClaimKind
    entities: tuple[str, ...]
    numbers: tuple[str, ...]
    sources: tuple[Source, ...]
    worth: float


@dataclass(frozen=True)
class Amend:
    id: str
    quote: str | None
    lekton: str | None
    numbers: tuple[str, ...] | None
    entities: tuple[str, ...] | None


@dataclass(frozen=True)
class Withdraw:
    id: str
    reason: str


@dataclass(frozen=True)
class Link:
    id: str
    relation: Relation
    other: str


Action = Add | Amend | Withdraw | Link


@dataclass(frozen=True)
class Ledger:
    claims: tuple[Claim, ...] = ()
    minute: int = 0
    next_id: int = 1
    rejected: tuple[str, ...] = field(default=())  # actions that named a claim that does not exist, kept for review

    def get(self, claim_id: str) -> Claim | None:
        return next((c for c in self.claims if c.id == claim_id), None)


def step(ledger: Ledger, minute: int, actions: Sequence[Action]) -> Ledger:
    """Apply one minute's actions. Unknown ids are not guessed at: the action is recorded in `rejected`."""
    claims = list(ledger.claims)
    next_id = ledger.next_id
    rejected = list(ledger.rejected)
    tag = f"m{minute}"

    def index(claim_id: str) -> int | None:
        return next((i for i, c in enumerate(claims) if c.id == claim_id), None)

    for a in actions:
        if isinstance(a, Add):
            claims.append(
                Claim(
                    id=f"c{next_id}",
                    speaker=a.speaker,
                    at_ms=a.at_ms,
                    quote=a.quote,
                    lekton=a.lekton,
                    kind=a.kind,
                    entities=a.entities,
                    numbers=a.numbers,
                    sources=a.sources,
                    worth=min(1.0, max(0.0, a.worth)),
                    history=(f"{tag} add",),
                )
            )
            next_id += 1
            continue
        i = index(a.id)
        if i is None:
            rejected.append(f"{tag} {type(a).__name__.lower()} {a.id}: no such claim")
            continue
        c = claims[i]
        if isinstance(a, Amend):
            claims[i] = replace(
                c,
                quote=a.quote or c.quote,
                lekton=a.lekton or c.lekton,
                numbers=a.numbers if a.numbers is not None else c.numbers,
                entities=a.entities if a.entities is not None else c.entities,
                history=(*c.history, f"{tag} amend"),
            )
        elif isinstance(a, Withdraw):
            claims[i] = replace(c, status="withdrawn", history=(*c.history, f"{tag} withdraw: {a.reason}"))
        elif index(a.other) is None or a.other == a.id:
            rejected.append(f"{tag} link {a.id}→{a.other}: no such other claim")
        else:
            claims[i] = replace(c, links=(*c.links, (a.relation, a.other)), history=(*c.history, f"{tag} link"))
    return Ledger(claims=tuple(claims), minute=minute, next_id=next_id, rejected=tuple(rejected))


def minute_window(items: Sequence[Utterance], minute: int, context: int = CONTEXT_MINUTES) -> tuple[str, str]:
    """(context text, new-minute text) for minute `minute` (1-based: minute 1 is 0:00–1:00), one line per
    utterance: `[mm:ss] S2: text`. An utterance belongs to the minute it starts in."""
    new_lo, new_hi = (minute - 1) * MINUTE_MS, minute * MINUTE_MS
    ctx_lo = max(0, new_lo - context * MINUTE_MS)

    def lines(lo: int, hi: int) -> str:
        return "\n".join(f"[{clock(u.start_ms)}] {u.label}: {u.text}" for u in items if lo <= u.start_ms < hi)

    return lines(ctx_lo, new_lo), lines(new_lo, new_hi)


def ledger_digest(ledger: Ledger, limit: int = 80) -> str:
    """What the extractor sees of the ledger: one line per claim, newest last."""
    rows = [
        f"{c.id} [{clock(c.at_ms)}] {c.speaker} {c.kind}{' WITHDRAWN' if c.status == 'withdrawn' else ''}: {c.lekton}"
        for c in ledger.claims[-limit:]
    ]
    return "\n".join(rows) or "(empty)"
