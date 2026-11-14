"""The claim extractor: an OpenRouter chat model answering in a strict JSON schema (spike-plan §8).

One flat action object per item (`op` says which), every field present and nullable: a strict schema that every
provider accepts. The answer is parsed with pydantic at the boundary (ADR-001) and turned into domain actions;
anything malformed is reported, never guessed at. Answers are returned verbatim for saving (ADR-003).
"""

import json
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any, Final, Literal, get_args

from pydantic import BaseModel, ConfigDict, SecretStr, ValidationError

from lektyra.domain.claims import Action, Add, Amend, ClaimKind, Link, Relation, Source, Withdraw
from lektyra.domain.timefmt import parse_clock

ENDPOINT: Final = "https://openrouter.ai/api/v1/chat/completions"
DEFAULT_MODEL: Final = "google/gemini-3.5-flash"
TIMEOUT_S: Final = 180
RETRIES: Final = 4
BACKOFF_S: Final = (5.0, 15.0, 30.0, 60.0)

SYSTEM: Final = """You read a live Slovak political broadcast, one minute at a time, for a team that fact-checks
politicians. You extract only CHECKABLE FACTUAL CLAIMS: statements that data can prove or disprove.

Worth extracting: sums of money, budgets, salaries, prices, percentages and statistics; public contracts and
procurement; companies, their owners and their deals with the state; votes, bills and laws in the National Council
(NR SR) and government decisions; dates and who did what when; quotes attributed to other people; concrete promises
with a number or a date.
Not worth extracting: opinions, insults, predictions, rhetoric, vague statements without a checkable core, and
moderators' questions (unless the moderator states a fact).

For every claim:
- quote: the words as said, at most 30 words, in Slovak;
- lekton: ONE self-contained Slovak sentence with the checkable core - who, what, how much, when - with pronouns
  resolved from the context ("Vláda Roberta Fica v roku 2024 ..." not "My sme ...");
- kind: number | money | contract | company | vote | law | date | quote | promise | other;
- entities: persons, parties, institutions, companies named; numbers: the figures as said (with units);
- sources where it can be checked: crz (central register of contracts), ministry_invoices, nrsr (parliament votes,
  bills), finstat (companies, owners, financials), budget, statistics (Statistical Office), eu_funds, media, other;
- worth from 0 to 1: how valuable checking it is (a concrete figure, name or date about public money: high; vague: low);
- speaker: the label exactly as given (S1, S2, ?). Never guess who the person is.

Rules:
- Extract claims spoken in NEW MINUTE only. CONTEXT is earlier transcript, already processed: use it to understand.
- If NEW MINUTE completes or corrects a claim already in LEDGER: "amend" it (by its id) instead of adding it again.
- If the speaker takes a claim back or corrects himself: "withdraw" it (with the reason) and "add" the corrected one.
- If a claim supports, contradicts or repeats one in LEDGER: "link" it (relation, the other id).
- Use only ids that are in LEDGER. If nothing checkable was said: return no actions.
- The transcript comes from speech recognition: a misheard name or number may be wrong; keep it as written."""


END_PASS: Final = """You are given the WHOLE transcript of a Slovak political broadcast and the LEDGER of checkable
claims that was built live, one minute at a time. Review the whole picture, the way a careful editor does after the
show:

1. "add" checkable claims the live pass MISSED (same standard as live: data can prove or disprove them).
2. "link" claims across the whole event: a later statement that contradicts, supports or repeats an earlier one,
   including a speaker contradicting himself or another speaker.
3. "withdraw" exact duplicates (reason: "duplicate of cN") and claims the speaker later corrected or took back
   (reason: what changed; then "add" the corrected claim if it is not in the ledger).
4. "amend" a claim whose meaning only becomes clear from later context (e.g. who "they" were, which year).

Same fields and rules as live: quote, lekton (one self-contained Slovak sentence), kind, entities, numbers, sources,
worth, speaker label exactly as given (never guess who the person is). "at" is the mm:ss or h:mm:ss where it was said.
Use only ids that are in LEDGER. Do not re-add claims already in LEDGER."""


def _nullable(t: str) -> dict[str, Any]:
    return {"type": [t, "null"]}


def _enum_or_null(values: tuple[str, ...]) -> dict[str, Any]:
    return {"type": ["string", "null"], "enum": [*values, None]}


def _list_or_null(items: dict[str, Any]) -> dict[str, Any]:
    return {"type": ["array", "null"], "items": items}


_FIELDS: Final[dict[str, dict[str, Any]]] = {
    "op": {"type": "string", "enum": ["add", "amend", "withdraw", "link"]},
    "id": _nullable("string"),
    "speaker": _nullable("string"),
    "at": _nullable("string"),
    "quote": _nullable("string"),
    "lekton": _nullable("string"),
    "kind": _enum_or_null(get_args(ClaimKind)),
    "entities": _list_or_null({"type": "string"}),
    "numbers": _list_or_null({"type": "string"}),
    "sources": _list_or_null({"type": "string", "enum": list(get_args(Source))}),
    "worth": _nullable("number"),
    "reason": _nullable("string"),
    "relation": _enum_or_null(get_args(Relation)),
    "other": _nullable("string"),
}
SCHEMA: Final[dict[str, Any]] = {
    "type": "object",
    "properties": {
        "actions": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": _FIELDS,
                "required": list(_FIELDS),
                "additionalProperties": False,
            },
        }
    },
    "required": ["actions"],
    "additionalProperties": False,
}


class _Item(BaseModel):
    model_config = ConfigDict(extra="ignore")
    op: Literal["add", "amend", "withdraw", "link"]
    id: str | None = None
    speaker: str | None = None
    at: str | None = None
    quote: str | None = None
    lekton: str | None = None
    kind: ClaimKind | None = None
    entities: list[str] | None = None
    numbers: list[str] | None = None
    sources: list[Source] | None = None
    worth: float | None = None
    reason: str | None = None
    relation: Relation | None = None
    other: str | None = None


class _Answer(BaseModel):
    actions: list[_Item]


class _Message(BaseModel):
    model_config = ConfigDict(extra="ignore")
    content: str | None = None


class _Choice(BaseModel):
    model_config = ConfigDict(extra="ignore")
    message: _Message


class _Usage(BaseModel):
    model_config = ConfigDict(extra="ignore")
    cost: float | None = None
    prompt_tokens: int | None = None
    completion_tokens: int | None = None


class _Completion(BaseModel):
    model_config = ConfigDict(extra="ignore")
    choices: list[_Choice]
    usage: _Usage | None = None


@dataclass(frozen=True)
class RawCompletion:
    status: int
    body: str
    wall_ms: int


@dataclass(frozen=True)
class Parsed:
    actions: list[Action]
    problems: list[str]
    cost_usd: float | None


def to_actions(items: list[_Item], minute_start_ms: int) -> tuple[list[Action], list[str]]:
    actions: list[Action] = []
    problems: list[str] = []
    for n, it in enumerate(items):
        try:
            if it.op == "add":
                if not (it.lekton and it.speaker and it.kind):
                    raise ValueError("add needs lekton, speaker and kind")
                at_ms = parse_clock(it.at) if it.at else minute_start_ms
                actions.append(
                    Add(it.speaker, at_ms, it.quote or it.lekton, it.lekton, it.kind, tuple(it.entities or ()),
                        tuple(it.numbers or ()), tuple(it.sources or ()), it.worth if it.worth is not None else 0.5)
                )  # fmt: skip
            elif it.op == "amend":
                if not it.id:
                    raise ValueError("amend needs an id")
                ents = tuple(it.entities) if it.entities is not None else None
                nums = tuple(it.numbers) if it.numbers is not None else None
                actions.append(Amend(it.id, it.quote, it.lekton, nums, ents))
            elif it.op == "withdraw":
                if not it.id:
                    raise ValueError("withdraw needs an id")
                actions.append(Withdraw(it.id, it.reason or ""))
            else:
                if not (it.id and it.other and it.relation):
                    raise ValueError("link needs id, relation and other")
                actions.append(Link(it.id, it.relation, it.other))
        except ValueError as problem:
            problems.append(f"action {n} ({it.op}): {problem}")
    return actions, problems


def parse(body: str, minute_start_ms: int) -> Parsed:
    """A chat completion → domain actions. Raises ValueError when the body is an error or not the schema."""
    try:
        data: Any = json.loads(body)
    except json.JSONDecodeError as err:
        raise ValueError(f"not JSON: {err}") from err
    if isinstance(data, dict) and isinstance(data.get("error"), dict):
        raise ValueError(" ".join(str(data["error"].get("message")).split())[:300])
    try:
        completion = _Completion.model_validate(data)
        content = completion.choices[0].message.content or '{"actions": []}'
        answer = _Answer.model_validate_json(content)
    except (ValidationError, IndexError) as err:
        raise ValueError(f"not the expected schema: {str(err)[:300]}") from err
    actions, problems = to_actions(answer.actions, minute_start_ms)
    return Parsed(actions, problems, completion.usage.cost if completion.usage else None)


class OpenRouterClaimExtractor:
    def __init__(self, api_key: SecretStr, model: str = DEFAULT_MODEL) -> None:
        self._key = api_key
        self.model = model

    def ask(self, user: str, system: str = SYSTEM) -> RawCompletion:
        payload = {
            "model": self.model,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
            "response_format": {
                "type": "json_schema",
                "json_schema": {"name": "claim_actions", "strict": True, "schema": SCHEMA},
            },
            "temperature": 0,
            "usage": {"include": True},
        }
        started = time.monotonic()
        status, body = self._post(payload)
        for attempt in range(RETRIES):
            if status != 429 and status < 500:
                break
            time.sleep(BACKOFF_S[attempt])
            status, body = self._post(payload)
        return RawCompletion(status, body, round((time.monotonic() - started) * 1000))

    def _post(self, payload: dict[str, Any]) -> tuple[int, str]:
        request = urllib.request.Request(
            ENDPOINT,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self._key.get_secret_value()}",
                "Content-Type": "application/json",
                "X-Title": "lektyra",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=TIMEOUT_S) as response:
                raw: bytes = response.read()
                return response.status, raw.decode("utf-8", "replace")
        except urllib.error.HTTPError as err:
            return err.code, err.read().decode("utf-8", "replace")
        except (TimeoutError, urllib.error.URLError) as err:
            return 599, json.dumps({"error": {"message": f"network: {err}"}})
