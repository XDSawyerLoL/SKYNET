# SKYNET

**Sovereign local-first governed personal AI for Windows.**

SKYNET owns the agent core and treats models, runtimes, connectors, channels, payment rails and external authorization systems as replaceable adapters. No paid API is required for the default setup.

Current milestone: **V0.9 — Product Convergence**

V0.9 is a deliberate product-convergence release: it closes practical gaps in multi-agent depth, sessions/history, integrations, skills, browser/web use, developer tooling, channels and automations before the first serious real-PC benchmark.

## What V0.9 adds

- Durable **sessions** with titles, projects, channels, archive state, full-history search and session forking.
- Desktop session switcher, new/fork/search UX and conversation resume.
- **Progressive skill disclosure**: relevant approved skills are loaded automatically for a task instead of dumping the whole skill library into context.
- Read-only support for external `SKILL.md` directories through `SKYNET_SKILL_DIRS` while keeping SKYNET's approved internal skills as the trust source of truth.
- Local skill usage evidence to improve future relevance ranking.
- A deeper **hierarchical multi-agent graph** with planner, researcher, analyst, coder, security, critic and verifier dependencies plus persistent run traces.
- Subagents remain reasoning-only; they do not inherit SKYNET's tool authority.
- A **local browser harness** with dependency-free read-only HTTP mode and optional interactive Playwright/Chromium.
- Playwright runs on a dedicated browser worker thread so Desktop, automations and channels can share one browser state safely.
- A persistent **Integration Registry** with capability indexing, built-in capability declarations, MCP discovery and manifest-based future adapters.
- Configured MCP tools can be surfaced directly as native `mcp__server__tool` tools while still crossing Mandate + PermissionGate + Receipt enforcement.
- A persistent channel-neutral **inbox/outbox** and an opt-in authenticated loopback webhook bridge.
- Channel sessions cannot remotely self-approve sensitive actions.
- Conversation-bound automations, one-shot jobs and bounded run counts.
- A bounded **developer toolkit**: doctor, project tree, source search, git status/diff/log and permission-gated unit-test execution.
- `skynet-admin` product/developer console.
- Thread-safe SQLite stores for Desktop/automation/channel concurrency.

V0.9 keeps the V0.8 Trust & Resilience layer: supervisor/heartbeat, crash-loop protection, global kill-switch, signed validation reports, historical failure regressions, verified backup/import and Windows DPAPI full-identity backup. It also keeps the V0.7 Adaptive Lab, measured model evolution, telemetry, resource-aware routing, Red Team, risk budgeting, canary/rollback, Mandates, signed receipts, Windows UI Automation, vision fallback and local memory.

## Product architecture

```text
                       SKYNET V0.9
                           │
                    Sovereign Core
                           │
      ┌────────────────────┼─────────────────────┐
      │                    │                     │
   Sessions             Memory                Skills
 history/search       semantic + facts      progressive
 fork/projects        trajectories          disclosure
      │                    │                     │
      └────────────────────┼─────────────────────┘
                           │
                      Main Agent
                           │
                    Model Router
                           │
              ┌────────────┴────────────┐
              │                         │
       Hierarchical Swarm         Single-agent path
              │                         │
              └────────────┬────────────┘
                           │
                    GLOBAL KILL SWITCH
                           │
                    Canonical Mandate
                           │
                 Deterministic Policy
                           │
                    PermissionGate
                           │
                        Tool Bus
          ┌────────┬───────┼───────┬─────────┐
          │        │       │       │         │
       Windows   Browser   MCP    Files      Dev
          │        │       │       │         │
          └────────┴───────┼───────┴─────────┘
                           │
                  Evidence + Receipt
                           │
                   Trajectory / Evals
```

## Multi-agent depth

The default complex-task graph is dependency-aware rather than a flat fan-out:

```text
planner ─────────────┐
researcher ──────────┼─────────────┐
analyst ──────┬──────┘             │
              ├─ implementation ───┼─ critic ──┐
              └─ security ─────────┘           ├─ verifier
                                               │
                                         lead synthesis
```

Specialists are bounded local reasoning workers. They do **not** receive independent Windows/browser/MCP authority. Tool execution remains centralized behind SKYNET's deterministic governance boundary.

Inspect traces:

```powershell
.\.venv\Scripts\skynet-admin.exe swarm-runs
```

## Sessions and history

The Desktop UI can create, switch, fork and search sessions. Sessions can also be grouped by project/channel metadata.

CLI inspection:

```powershell
.\.venv\Scripts\skynet-admin.exe sessions
.\.venv\Scripts\skynet-admin.exe session-search "browser failure"
.\.venv\Scripts\skynet-admin.exe session-fork <session_id>
```

Forking copies recent history into a new independent session so experiments can diverge without losing the original conversation.

## Progressive skills

SKYNET ranks approved skills against the current request and loads only the most relevant procedures into context. Usage is tracked locally.

```powershell
.\.venv\Scripts\skynet-admin.exe skill-usage
```

Optional external skill directories can be added without copying them into SKYNET:

```text
SKYNET_SKILL_DIRS=C:\path\to\skills
```

A directory containing `my-skill\SKILL.md` becomes discoverable read-only. External skills do not gain executable authority merely by being present.

## Browser / web

The core always supports read-only HTTP navigation and extraction using Python's standard library.

For interactive local Chromium:

```powershell
powershell -ExecutionPolicy Bypass -File .\install-browser.ps1
```

This installs Playwright and Chromium locally. No cloud browser is required.

Interactive browser actions such as clicks, typing and screenshots remain permission-gated. Browser/webpage content is always treated as untrusted data.

## Integrations and MCP

Inspect enabled capabilities:

```powershell
.\.venv\Scripts\skynet-admin.exe integrations
.\.venv\Scripts\skynet-admin.exe capabilities
.\.venv\Scripts\skynet-admin.exe tools
```

Configured MCP servers remain replaceable adapters. V0.9 can introspect their tool schemas and expose them directly to the model as:

```text
mcp__<server>__<tool>
```

Dynamic MCP tools are **confirmation-required by default**, risk-classified like explicit MCP calls and included in signed receipts.

Integration manifests under `.skynet/integrations.d/*.json` are declarative metadata only; a manifest cannot grant itself executable authority.

## Channels

V0.9 provides a durable channel-neutral inbox/outbox plus an authenticated local webhook bridge. It is infrastructure for Telegram/Discord/Slack/email/etc. adapters; it is **not a claim that every provider-specific adapter ships built in yet**.

Set a private local token in `.env`:

```text
SKYNET_WEBHOOK_TOKEN=<your-random-secret>
SKYNET_CHANNEL_HOST=127.0.0.1
SKYNET_CHANNEL_PORT=8765
```

Then launch explicitly:

```powershell
.\.venv\Scripts\skynet-channel.exe
```

Inbound adapter contract:

```text
POST /inbound/<channel>/<peer>?session=<session_id>
Authorization: Bearer <token>
{"content":"message"}
```

Outbound adapters poll:

```text
GET /outbox
Authorization: Bearer <token>
```

The bridge binds to loopback by default and refuses a remote bind unless `SKYNET_ALLOW_REMOTE_CHANNEL_BIND=1` is explicitly set.

## Automations

Automations are now bound to sessions so scheduled work can continue the correct conversation context.

Existing interval routines remain supported. V0.9 also supports one-shot and bounded jobs.

```powershell
.\.venv\Scripts\skynet-admin.exe automations
.\.venv\Scripts\skynet-admin.exe automation-once 300 <session_id> "check the result and summarize changes"
```

Unattended execution still cannot approve confirmation-required actions.

## Developer tooling

```powershell
.\.venv\Scripts\skynet-admin.exe doctor
```

The governed agent can use bounded developer tools for:

- project tree;
- source search;
- git status;
- git diff;
- recent commits;
- local unit tests.

Reading is non-mutating. Test execution runs local project code and therefore requires confirmation.

## Install on Windows

Requirements:

- Windows 10/11
- Python 3.11+
- Git
- Ollama

```powershell
git clone https://github.com/XDSawyerLoL/SKYNET.git
cd SKYNET
powershell -ExecutionPolicy Bypass -File .\install.ps1
ollama pull qwen3:8b
```

Desktop:

```powershell
powershell -ExecutionPolicy Bypass -File .\launch.ps1
```

Core CLI:

```powershell
.\.venv\Scripts\skynet.exe
```

Product/developer console:

```powershell
.\.venv\Scripts\skynet-admin.exe status
```

Evolution lab:

```powershell
.\.venv\Scripts\skynet-evolve.exe status
```

Trust/resilience console:

```powershell
.\.venv\Scripts\skynet-trust.exe status
```

Supervisor:

```powershell
.\.venv\Scripts\skynet-supervisor.exe
```

## Global stop and resilience

Emergency stop:

```powershell
powershell -ExecutionPolicy Bypass -File .\emergency-stop.ps1
```

Re-arm only explicitly:

```powershell
powershell -ExecutionPolicy Bypass -File .\rearm.ps1
```

The kill-switch is checked below model reasoning before policy/tool execution. Crash loops stop autonomy rather than restarting forever.

## Sovereignty rules

1. Models remain replaceable.
2. Sessions, memories, trajectories, skills, policies, receipts, telemetry and deployment state stay local by default.
3. No paid/cloud API is required for core operation.
4. The LLM never authorizes its own consequential action.
5. Subagents do not automatically inherit tool authority.
6. Dynamic integrations remain behind deterministic policy and permissions.
7. External skills/manifests are data until explicitly trusted/promoted.
8. Web/channel/tool output is untrusted input, never higher-priority instruction.
9. The global kill-switch remains beneath model reasoning.
10. Historical failures become regression tests instead of being forgotten.
11. Improvement promotion remains measured, canary-based and rollback-capable.
12. SKYNET does not claim provider-specific integrations until their adapters actually exist and are tested.

## Next phase: real-PC benchmark

V0.9 is intentionally the convergence release before field testing. The next milestone is not another feature dump: it is a **Reality Benchmark** on the target Windows PC measuring real task success, intervention rate, false-success rate, recovery, steps, latency, resource pressure and permission fatigue.

See `docs/V0.9.md` for architecture and benchmark entry criteria.
