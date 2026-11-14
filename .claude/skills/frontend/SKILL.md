---
name: frontend
description: How the lektyra UI (web/) is built — React + TypeScript strict + TanStack Query + React Router + zod + sonner, one API wrapper, AppError, QueryView, design tokens, no effects. Use before writing or changing anything under web/, or the review API it talks to.
---

# Frontend (web/)

The UI is a local review tool (ADR-009): Vite, React 19, TypeScript strict, TanStack Query for every server
state, React Router, zod at the boundary, sonner for toasts, CSS Modules on design tokens. `lektyra ui` serves
the built `web/dist` and the JSON API under `/api` on 127.0.0.1.

## Where things go

```
web/src/
  app/            the shell: App (providers), router, AppShell (sidebar), RouteError
  platform/       shared, feature-agnostic
    api/          apiRequest / apiSend / apiUrl / seg — the ONLY way to call the server; AppError, toAppError
    query/        createQueryClient: retries and the one place errors become toasts
    ui/           the kit: Button, IconButton, Card, Badge, Field/TextInput/TextArea/Checkbox, Dialog, Popover,
                  Stars, PageHeader, QueryView/Skeleton/EmptyState/ErrorPanel, Icon, LogoMark, voiceColor
    format/       clock, talkTime, count (plurals), engineName, dates
    theme/        tokens.css (every colour, size, radius), base.css
    routing.ts    useRequiredParam
  features/<name>/
    api.ts        zod schemas + types + queryOptions + mutation hooks for this feature
    *.tsx         its screens and parts; *.module.css next to them
```

A feature imports from `platform/` and, sparingly, another feature's `api.ts` or a shared part
(`SpeakerNaming`, `PersonPicker`). `platform/` never imports a feature.

## Rules (enforced by ESLint and the L9 hook)

- **No casts, no `!`, no `any`, no `@ts-ignore`, no `eslint-disable`** (skill code-style). Data from the server
  is parsed by the feature's zod schema inside `apiRequest`; a mismatch is an AppError `contract`, not a crash.
- **No `useEffect`.** Server data → `useQuery`; a value from props → compute it; one-off state →
  `useState(() => …)`; reacting to a click → the handler; DOM work on mount → a ref callback (Dialog opens with
  `showModal()` in one); a form reset → `key` the component.
- **No raw `fetch`.** `apiRequest(path, schema, { method, body, signal })` or `apiSend` (204). URLs build path
  segments with `seg()`.
- **Errors are shown once:** a query with nothing on screen → `QueryView` renders `ErrorPanel` (with *Try again*
  only when asking again can help); a failing refresh or a mutation → a toast from the query client. A form that
  shows its own field errors sets `meta: { silent: true }` and reads `error.fieldMessage('name')`. Success toasts:
  `meta: { success: '…' }` or the hook's `onSuccess` when the text needs the variables.
- **Every mutation invalidates what it changes**, by key prefix. Naming changes guesses in every video, so it
  invalidates `['events']`, `['persons']`, `['voices']`; transcripts (`['transcripts', …]`) never change while
  read and are not refetched.
- **Styling:** CSS Modules with tokens only (`var(--signal)`, `var(--s4)`), never a raw colour or pixel size
  outside `tokens.css`. Speakers wear `voiceColor(label)` in a fixed order; status colours never mark a series.
  Font: Segoe UI Variable (Martin chose it), Cascadia Mono for times.
- **Accessibility:** every control has a name (IconButton's `label`, Field wires label/hint/error), keyboard works
  (the timeline is a slider, Stars a radio group, Popover and Dialog are native), colour is never the only signal.
- **The API speaks one error shape** `{"error": {"code", "message", "details"}}` (adapters/web/api.py); messages
  are written for Martin and never carry a key, a path or a voice.

## Gates

`npm run check` in `web/` (typecheck, lint, Vitest); `npm run build` must stay clean. Pure logic (time lookups,
formatting, the API wrapper) gets Vitest tests; screens get a **manual-testing** walk with screenshots read back
— that is the bar for a UI change, not end-to-end tests. The API has its own integration test
(`tests/integration/test_review_api.py`, needs Postgres).
