# Board operations for the crew UI — review, design, contracts

Scope decision (owner, 2026-11-19): give the Crew UI full board-task operations, **API-first** so every
operation is equally callable by AI agents/bots over HTTP with a session token — the UI is only a mask
over the same routes. Kanban graph stays read-only (its value is the safe overview; the "Open in Crew"
cross-link is the act path).

## Review verdict — what earns its place

| # | Operation | User value | Agent/bot value | Risk | Verdict |
|---|---|---|---|---|---|
| 1 | `POST /cards` — create, structured fields | High: intake without waiting for chat | High: same route for bots; `idempotency_key` for retries | Low (wraps the proven `hermes kanban create` CLI) | **Build (P1a)** |
| 2 | Board-aware `card_url` | High: links pasted in chats open the right board | **Highest**: it is the collaboration surface — every `crew_notify` message carries it; without a board it reproduces the 404 the owner hit | Low | **Build (P1b) — found during review** |
| 3 | Archive action + UI button | Medium: closes the lifecycle by hand | Medium: bots can retire cards they own | Low | **Build (P1c)** |
| 4 | Move card across boards | Medium-high: the fix-it tool for "card born on the wrong board" (a real incident: stale `current` pointer) | Medium | Medium: cross-DB copy + files | **Build (P2), guarded** |
| 5 | kg write actions | — | — | Destroys kg's read-only nature | **No** |
| 6 | New auth for bots | — | — | Session tokens already exist (`X-Hermes-Session-Token`) | **No — document instead** |

The UI create form is agent-ready **by construction**: Goal / Done when / Verify / Assignee / Model are
its fields (the `/crew` template), so a card a human types there is runnable by a worker bot without a
chat turn in between. That is the point of "support for AI agents/bots".

## Contracts (all POST, session-authed, board from the body)

### P1a — POST /cards
```json
{ "title": "...", "board": "<slug>", "body": "...", "assignee": "crew-worker",
  "model": "...", "provider": "...", "priority": 3, "skills": ["s"], "max_runtime": 7200,
  "goal": false, "created_by": "ui:serus", "idempotency_key": "..." }
```
→ `{ "ok": true, "card": { "id": "t_..", ... }, "board": "<slug>" }` (the CLI's own `--json` card).
Fails: 400 empty/oversized title, 404 unknown board, 400 CLI refused (stderr text returned).
Implementation: subprocess `hermes kanban --board <slug> create <title> --json [--body-file -] ...` —
argv list (no shell), `--body-file -` so newlines and flag-like lines survive; the render cache is
invalidated after the write. The board is an explicit argv flag (not env) so the create is never a
function of the request's own override. `created_by` lets the UI/bots mark provenance; agents use
`idempotency_key` for safe retries.

### P1b — board-aware card_url
`card_url(card_id, base=None, board=None)` appends `&board=<slug>` whenever the board is known
(`crew_card.board_slug(crew_card.kanban_db())` — correct under worker env pins and under request
overrides alike). Every notify path keeps calling the same function; bare `/crew?card=<id>` links
(from older messages) mean the active board, exactly like the UI contract.

### P1c — POST /action/archive (action framework)
`_ACTION_NAMES += "archive"`; `crew_card.archive_card(card)`: refuses a running card (use `stop`,
which parks and archives), else `_kanban(["archive", card])` — the board rides via `_child_env()`
(the proven fix). UI: an Archive button on the card page.

### P2 — POST /cards/move
```json
{ "card": "t_..", "to_board": "<slug>" }
```
`crew_card.move_card(card, to_slug)`, one transaction-ish copy between two board DBs:
- Guards: unknown target → CLI 2/404 semantics; source running/claimed (`status='running'` or
  `worker_pid`) → refused (stop first); target already has the id → idempotent no-op when the title
  matches, 409 otherwise.
- Copies: `tasks` row (same id), `task_comments`, `task_events`, `task_runs`, `task_attachments`
  **plus the files** under `boards/<src>/attachments/<id>/` (stored_path is absolute per board — rows
  are rewritten to the target board's absolute path).
- Links are board-local: v1 drops them and leaves a comment naming them.
- Source card: archived with a pointer comment ("Moved to <board>/<id>"); a comment on the target
  names the origin. Nothing is deleted — the trail survives on both boards.
- UI: a Move-to-board picker on the card page; on success the app navigates to the card on the new
  board (the withBoard link).

### P3 — assignees for the form
The create form's assignee field is a plain input (validated by the dispatcher on pickup); a
`/assignees.json` (CLI `hermes kanban assignees`) can follow later if the free-text field annoys.

## UI (masks over the routes, nothing more)
- Board page header, next to the switcher: **`+ New card`** — title, board (prefilled with the view's
  board), Goal/Done-when/Verify textarea (the agent template), assignee, model; POST /cards → refresh.
- Card page: **Archive** (P1c), **Move to board…** (P2) in the action row.
- kg: unchanged, read-only.

## Tests, review, deploy
- Extend the fastapi test set (env -u PYTHONPATH): create (mocked subprocess + a real temp board),
  archive guard, move happy/running/idempotent/unknown-board cases on temp boards.
- Full suite + kg suite, codex review round, push forks.
- Deploy wave: restart dashboard 9119 + serve 9121 **and the gateway (9120)** — the gateway restart
  is already owed to the owner for the live 404/switcher fix; this wave pays both debts at once.
