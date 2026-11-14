# ADR-014: lektyra is a personal project and checks against its own data

*Status: accepted · 2026-11-14 · Martin ("repo lives here as my personal project now … remove ps-mcp things to use
we will use own one … name it all as personal thing")*

## Context

lektyra started on Martin's own initiative: his time, his hardware, his accounts and keys, public video. Early
notes were written next to other work and named a client's data server as the place quick checks would ask. That
blurs whose the product is, and it would make lektyra depend on someone else's infrastructure.

## Decision

1. **lektyra is Martin Fric's personal project.** The repository is `git@github.com:MartinFric/lektyra.git`, under
   his account and personal e-mail, with the proprietary LICENSE from the first commit (b449ca0, 2026-11-14 17:32).
2. **Nothing from any client goes in**: no client data, servers, repositories, keys or paid hours. Concepts, plans
   and decisions live in this repository only (`docs/plans/concept.md`, `spike-plan.md`, `docs/adr/`).
3. **Checks run against lektyra's own public-data service.** lektyra ingests public registers itself into its own
   Postgres and answers its quick checks from there (K21):
   - CRZ (central register of contracts): open data, every contract with its parties, amounts and dates;
   - NR SR: votes, prints and bills;
   - company registers (RPO / ORSR open data);
   - state budget and statistics where they are published as data.
   Each record keeps its source id and the date it was fetched, so a verdict names the exact record and the state of
   the register it saw (ADR-010).
4. Any integration for a particular customer is an adapter outside the core, under its own terms.
5. **lektyra can be licensed or handed over, to a client too, once Martin is happy with the terms** (Martin: "it can
   be handed – once i am happy with terms"). Until terms are agreed, nothing of it (code, data, know-how) goes over;
   it is shown running, not delivered.

## Consequences

- K21 is a real piece of work (ingest and refresh of public registers) instead of a call to someone else's server.
  The engine and its data are lektyra's own, and they serve any customer.
- ADR-010 is amended: "our data" means this service.
- The board holds no client tasks.

## Enforced by

AGENTS.md ("nothing from any client"), review, and the repository's history.
