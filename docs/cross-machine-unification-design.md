# Cross-machine unification design — native kanban + kanban-graph + crew on both gateways

Status: DESIGN (owner-requested 2026-11-23, pre-implementation). Scope: the ecosystem runs on BOTH
sides — the VPS webapp (hermes.serus-devops.site) and the Windows desktop (lts-dev01) — with the
SAME custom plugins, cards viewable and operable regardless of origin, gateway, profile or model.

## 0. The owner's division of labor (the target shape)

- **Clara** — VPS/Linux. Owns lts / ATGZ / SAI tasks, the webapp, the shared infra.
- **Freya** — Windows (lts-dev01). Owns bridge / Windows / CHG tasks.
- Both are member agents on their own gateways. The BOARD is the collaboration medium, not the
  gateway link.

## 1. Verified ground truth (2026-11-23)

| Fact | Where |
|---|---|
| SSH-kind connections support only Linux/macOS remotes — both server-side and Electron. Windows remotes are blocked at the serve-lifecycle gate (upstream is building toward it: `windows-remote-inventory.ts` exists) | `gateway_connections_ssh_remote.py` `SUPPORTED_REMOTE_OS`; `remote-lifecycle.ts:43` |
| URL-kind connections are OS-agnostic: they need an authenticated HTTP+WS endpoint. `hermes serve` works on Windows; lts-dev01's `dashboard.basic_auth` is empty (a public bind refuses until set); ports 9119/9120/9121/8644 are free there | live probes on lts-dev01 |
| The dispatcher claims a card only when its assignee resolves to an existing profile (`profile_exists` gate) — ANY profile, not just crew roles | `crew_card.py:591` |
| Per-card model override exists (`hermes kanban set-model <id>`) and empties to the role profile's model; providers must resolve in the worker's profile | `crew_card.py:788,1110` |
| Cards without GOAL/DONE sections degrade (goal="") — the crew view already tolerates non-crew shapes structurally | `crew_card.py:820` |
| Cross-machine assignment is official via "Shared boards across homes": one kanban.db in several homes + `kanban.dispatch_profiles` allowlist per home; never assign `default` on a shared board | upstream kanban docs |
| Our fork already ships: multi-board switcher, cross-links (crew↔kg deep links, board-carrying card_url), create/archive/move ops API-first (`POST /cards`, `POST /cards/move`, `POST /action/archive`) | feat/multi-board-crew `bdb6782`, feat/crew-crosslinks `03392a2`, codex-approved |
| Upstream crew plugin is installed on lts-dev01 (installer run 3, `--no-cron`) but NOT our custom fork | lts-dev01 plugins dir |
| The webapp's Gateways page supports per-connection "Make primary"; the plugin SDK exposes `connections()/agents()/ensureAgent()/warmAgent()` (multi-source agents) | webapp + `sdk/index.ts:752+` |

## 2. The five gaps this design closes

### Gap A — the same custom plugins on both machines (shared tools)

**Principle: the org forks are the SSOT.** `Aether-GenesiZ/Crew` (branch `feat/multi-board-crew`) and
`Aether-GenesiZ/hermes-kanban-graph` (`feat/crew-crosslinks`).

- VPS already runs the fork from `~/.hermes/plugins/{crew,kanban-graph}`.
- lts-dev01 gets the fork by cloning those repos into `%LOCALAPPDATA%\hermes\plugins\` (replacing the
  upstream copy) and re-running `install.py --no-cron` (or with cron once the dispatcher is piloted).
- **Windows-compat checklist (must verify before declaring parity):**
  1. `crew_card.py` uses `os.path` + the `hermes` CLI wrapper — the wrapper must resolve the Windows
     binary (`hermes.exe` path) the way `crew-run.sh` already does on that machine.
  2. `crew-run.sh` is a POSIX script; on Windows the equivalent entry must be `python crew_card.py …`
     directly (Git-for-Windows sh also works if present — decide one, document one).
  3. `_child_env()` board override is env-based — the Windows `hermes kanban` honors
     `HERMES_KANBAN_DB`/`--board` identically (verify with one probe card).
  4. The desktop bundle (`desktop/plugin.js`) is platform-neutral; `sh scripts/rebuild.sh` has a
     Windows path alternative (node build.mjs directly).
  5. kg's `:8799` serve shell is OPTIONAL on Windows (the desktop webapp serves the plugin); make it
     a non-goal there, keep the plugin-only install.
- Version discipline: pin both machines to the SAME fork commit; updating = `git pull` + installer +
  gateway restart; never let one side drift (a `crew --version`/`git rev-parse` stamp in the board.json
  payload is a cheap drift probe).

### Gap B — crew "full details" for cards not born from crew

**Principle: crew is a mask over the native kanban DB, never the owner of the cards.** A card created
by `hermes kanban create`, by a webhook, by the New-card form, or by another gateway's agent must get
the SAME detail surface as a crew template card.

Today the coupling points are three, all fixable without schema changes:

1. **GOAL/DONE parsing** already degrades; the detail page must SHOW the raw body when no GOAL
   section exists (render the body as the "pending reason" fallback) instead of an empty box.
2. **The action bar** (unstuck/retry/proof/stop/archive) gates on crew-ness implicitly through the
   worker spawn contract. Gate it on WHAT IS TRUE: a live/finished run owned by this machine — which
   is a property of the row (`worker_pid`, runs), not of the crew role. Cards with no runs show
   Unstuck/Archive only, never Stop/Proof (already the shape; keep it).
3. **The role strip / role preloads** apply only when the card carries a role (`crew.role` config on
   the assignee side); role-less cards render without the strip. No behavior forced.

Acceptance: a card created by native CLI with a plain body opens in crew with body, status, links,
comments, attachments, deep link to kg and back, and the archive action — zero crew templates
involved. (Our `POST /cards` already creates native-shaped cards, so the intake side is done.)

### Gap C — no lock to crew profiles, any gateway/profile/model

- **Profile**: the dispatcher's `profile_exists` gate is already the right rule — any existing
  profile on the claiming machine is claimable. What changes: the New-card form and create route
  treat assignee as free text (already true) and the DOCS state it; `role_profile()` stays as the
  crew-role convenience, never a requirement for viewing.
- **Model**: `set-model` + the create route's `--model` pass-through (already in `POST /cards`)
  cover per-card models; empty = the profile's own default. No allowlist in crew.
- **Gateway**: a card carries no gateway — the board DB is the contract. Whichever home has the DB
  (or its mount) and owns the assignee profile in `dispatch_profiles` claims and runs it. The crew
  VIEW on either machine reads the same board, so "from any gateway" = "on the shared board" (Gap E)
  plus, for the webapp's roster surfaces, the URL-kind connection (multi-source agents).

### Gap D — the trio behaves as one system (contracts)

The SSOT is the native kanban DB + CLI. The contracts, most already shipped in the fork:

| Contract | Status |
|---|---|
| crew→kg deep link `#/kanban-graph?task=<board>/<id>` | shipped |
| kg→crew `Open in Crew` → `/crew?card=<id>&board=<slug>` | shipped |
| `card_url` carries the board on every notify surface | shipped (codex-approved) |
| Board switching without moving the default pointer | shipped |
| Create / archive / move as API-first routes agents also POST | shipped (board-ops) |
| kg stays read-only; every write goes through native CLI or crew's routes | by design, keep |
| Native CLI can do everything without crew installed (crew never a dependency) | keep true |

Remaining work for D is verification, not construction: on both machines, click a card born from
native CLI through all three surfaces and confirm nothing 404s (the original owner's 404 is the
regression to never repeat).

### Gap E — shared board across homes + native multi-gateway

- **Shared board**: a DEDICATED joint board (suggested `joint-ops`), never the default board. The
  DB lives on the VPS (mature SQLite locking); lts-dev01 mounts the board dir read-write over
  Tailscale (sshfs-win/WinFsp), or the reverse if Windows-side proves stabler — decide by probe.
  Both homes set `kanban.dispatch_profiles` (VPS: clara + crew roles; lts-dev01: freya + its roles)
  and nothing else claims; `default` is never assigned there. First test: a card assigned `freya`
  created from the webapp, claimed and run ON Windows, result visible from the VPS.
- **Multi-gateway (native)**: the URL-kind connection — `hermes serve --host 0.0.0.0 --port 9121` on
  lts-dev01 once `dashboard.basic_auth` is set (owner approval pending), then
  `http://100.123.48.58:9121` in the webapp. That unlocks sessions/bots/profiles of the Windows
  backend from the domain and the SDK's multi-source agents (`ensureAgent/warmAgent`) for driving
  remote agents programmatically. Gateway links DO NOT carry kanban dispatch — that is Gap E's
  shared board, and the two are complementary, not alternatives.

## 3. Phasing

- **P0 — parity prep (no behavior change):** clone the forks onto lts-dev01 over the upstream
  plugin copy; run the Windows-compat checklist (A); one probe card through both plugins there.
- **P1 — universal card details (Gap B+C):** the body-fallback render + action-bar truth-gating in
  our fork; tests: native-CLI-born card e2e through crew actions; docs updated.
- **P2 — shared board pilot (Gap E):** mount + `dispatch_profiles` both sides + the first
  cross-machine card; watch SQLite-over-sshfs behavior for a week before widening.
- **P3 — multi-gateway polish:** serve on Windows (owner-gated) → URL-kind connection → verify
  "Make primary" plugin behavior + SDK multi-source agents; wire the roster the way Bot Mode
  already renders the union.

## 4. Risks / open decisions for the owner

1. Shared-board host direction (recommend VPS-hosted; reverse is acceptable if sshfs-win proves
   flaky).
2. `hermes serve` + `dashboard.basic_auth` on lts-dev01 — owner approval (work machine).
3. Whether the Windows dispatcher joins with cron now or stays pilot-paced (FS6 context).
4. Upstream drift: our fork vs upstream crew 0.10.9 — rebase discipline before any upstream Windows
   remote support lands (it will replace the URL-kind workaround eventually).
