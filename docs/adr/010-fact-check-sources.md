# ADR-010: Fact check: our data first, the web as fallback, two reliable sources

*Status: accepted · 2026-11-14 · Martin ("fallback … internet in some elegant way … anchored at least on 2 reliable
sources else it will be need to verify … filter out uninteresting claims – but store them")*

## Context

The claims loop produces checkable claims (spike-plan §8, board K10). Some can be checked against PS's own
data: CRZ contracts, ministry invoices, NR SR votes and prints, finstat. Many cannot: quotes, statistics, events.
A web search finds anything, including wrong things. A verdict that names a politician must not rest on one blog.

## Decision

1. **Our data first.** Each claim kind has its quick checks (K21): contract/amount → CRZ; company → finstat/CRZ;
   vote/bill → NR SR. A match or mismatch there is recorded as a source with its record id.
2. **The web as fallback.** It runs for claims our data cannot settle, or to corroborate it. Every result is
   classified by its publisher:
   - **official**: state and public bodies (gov.sk and its ministries, crz.gov.sk, nrsr.sk, slov-lex.sk,
     statistics.sk, Eurostat, …);
   - **established media**: an allowlist (TASR, STVR, SME, Denník N, Aktuality, Pravda, HN, TA3, …) kept in config
     and reviewed;
   - **other**: everything else. It is shown, never counted.
3. **The rule:**
   - **supported**: at least **2 independent reliable sources** (official or established, **different
     publishers**) support it, and none contradicts it;
   - **contradicted**: 2 such sources contradict it;
   - **needs verification**: anything else (one source, sources disagree, only "other").
   Our own data counts as one official source.
4. **Every verdict is a draft until a human confirms it.** Nothing leaves lektyra without that confirmation.
5. **Uninteresting claims are filtered, never deleted.** They are stored with the reason: opinion, no checkable
   core, a moderator's question, low worth. They can be reviewed and restored.
6. Each source is stored with URL, publisher, tier, date, the passage relied on, its stance (supports / contradicts /
   mentions) and when it was fetched, so a verdict can be re-examined later.

## Consequences

Some true claims stay "needs verification" when only one outlet reported them. That is the intended cost. The
allowlist is a decision with weight: changes to it are recorded (who, when, why).

Open: which search API (a search-enabled model through OpenRouter, or a search API with an LLM reading the results).
The decision follows a bake-off on A's claims (K22).

## Enforced by

`domain/verdict.py` (pure: tiers + the 2-source rule, unit-tested); the Fact check screen shows the rule and the
counted sources; review.
