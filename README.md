# SKYNET

**Sovereign local-first governed personal AI for Windows.**

SKYNET owns the agent core and treats models, runtimes, connectors, channels, payment rails and external authorization systems as replaceable adapters. No paid API is required for the default setup.

Current milestone: **V0.10 — Reality Accelerator**

V0.10 keeps the V0.9 Product Convergence stack and adds accelerated operational experience before the first serious real-PC benchmark. The objective is not to fake field history: it is to expose repeatable defects at machine speed, convert failures into regressions and arrive on the target PC with a much higher confidence floor.

## What V0.10 adds

- **Reality Accelerator** using real SKYNET persistence and policy components.
- Deterministic fault injection for duplicate deliveries, permission pressure, replay, risk overflow, expired mandates, session handoff, crash/reopen and unknown-tool injection.
- Windows CI now runs **1,000 synthetic operational hours** on every push in addition to the unit/integration suite.
- `skynet-sim core` for larger local soak campaigns such as 10,000+ episodes.
- **Model-in-the-loop synthetic arena**: the real local Ollama model uses the real SKYNET Agent loop against an isolated fake tool world with no filesystem/network/shell/desktop authority.
- Arena scenarios for prompt injection, verification discipline, denied approval, transient failures and impossible tasks where false success must be avoided.
- **Shadow trajectory analysis** for side-effect-free mining of suspicious historical behavior.
- Simulation failures can be promoted into the existing historical regression pipeline.
- **Idempotent channel delivery** through stable event/dedupe keys, including persistence across process restart.
- Webhook bridge support for `X-SKYNET-Event-ID` / JSON `event_id` so provider retries do not duplicate messages or replies.

Synthetic operational time is explicitly **not** claimed to be equivalent to literal human/physical-world hours. It is repeatable accelerated stress evidence. Real Windows field testing remains mandatory.

## Accelerated reality loop

```text
                  SKYNET V0.10
                       │
             Product Convergence
                       │
        ┌──────────────┼──────────────┐
        │              │              │
 deterministic      real local      historical
 core soak           LLM arena       shadow replay
        │              │              │
        └──────────────┼──────────────┘
                       ↓
                 failures/anomalies
                       ↓
              regression candidates
                       ↓
                  correction
                       ↓
                 repeat at scale
                       ↓
              REAL WINDOWS BENCHMARK
```

Run 10,000 synthetic episodes locally:

```powershell
.\.venv\Scripts\skynet-sim.exe core --episodes 10000 --workers 8 --strict
```

Run the configured Ollama model inside the isolated synthetic arena:

```powershell
.\.venv\Scripts\skynet-sim.exe agent --episodes 100 --model qwen3:8b
```

Analyze actual historical trajectories without tools or side effects:

```powershell
.\.venv\Scripts\skynet-sim.exe shadow --limit 1000
```

Convert deterministic simulation failures into regression seeds:

```powershell
.\.venv\Scripts\skynet-sim.exe promote-failures --limit 500
```

See `docs/V0.10.md` for the evidence model and limitations.

## V0.9 Product Convergence retained

- Durable **sessions** with titles, projects, channels, archive state, full-history search and session forking.
- Desktop session switcher, new/fork/search UX and conversation resume.
- **Progressive skill disclosure** with local usage evidence and read-only external `SKILL.md` support through `SKYNET_SKILL_DIRS`.
- Dependency-aware **hierarchical multi-agent graph** with planner, researcher, analyst, coder, security, critic and verifier plus persistent run traces.
- Subagents remain reasoning-only; they do not inherit SKYNET tool authority.
- Local browser harness with dependency-free HTTP read mode and optional Playwright/Chromium interactive mode on a dedicated browser thread.
- Persistent **Integration Registry** with capability indexing, MCP discovery and manifest-based adapters.
- Configured MCP tools can appear natively as `mcp__server__tool`, still behind Mandate + PermissionGate + Receipt enforcement.
- Persistent channel-neutral inbox/outbox and authenticated loopback webhook bridge.
- Conversation-bound automations, one-shot jobs and bounded run counts.
- Developer toolkit: doctor, project tree, source search, git status/diff/log and permission-gated unit-test execution.
- Thread-safe SQLite stores for Desktop/automation/channel concurrency.

## Core governance architecture

```text
Sessions / Memory / Skills / Trajectories
                 │
             Main Agent
                 │
            Model Router
          ┌──────┴──────┐
          │             │
 Hierarchical Swarm   direct path
          └──────┬──────┘
                 │
        GLOBAL KILL SWITCH
                 │
         Canonical Mandate
                 │
      Deterministic Policy Engine
                 │
          PermissionGate
                 │
             Tool Bus
   ┌────────┬────┼────┬────────┐
 Windows  Browser MCP Files  Developer
   └────────┴────┼────┴────────┘
                 │
       Evidence + signed Receipt
                 │
  Trajectory → Eval → Candidate → Canary/Rollback
```

The LLM may propose an action. It does not decide whether that action is authorized.

## Multi-agent depth

The complex-task graph is dependency-aware rather than a flat fan-out:

```text
planner ─────────────┐
researcher ──────────┼─────────────┐
analyst ──────┬──────┘             │
              ├─ implementation ───┼─ critic ──┐
              └─ security ─────────┘           ├─ verifier
                                               │
                                         lead synthesis
```

Inspect traces:

```powershell
.\.venv\Scripts\skynet-admin.exe swarm-runs
```

## Sessions and history

```powershell
.\.venv\Scripts\skynet-admin.exe sessions
.\.venv\Scripts\skynet-admin.exe session-search "browser failure"
.\.venv\Scripts\skynet-admin.exe session-fork <session_id>
```

Forking copies recent history into a new independent session so experiments can diverge without losing the original conversation.

## Progressive skills

```powershell
.\.venv\Scripts\skynet-admin.exe skill-usage
```

Optional external skill directories:

```text
SKYNET_SKILL_DIRS=C:\path\to\skills
```

External skills are read-only data until explicitly trusted/promoted. They do not gain executable authority by existing on disk.

## Browser / web

Read-only HTTP navigation works with the Python standard library. For interactive local Chromium:

```powershell
powershell -ExecutionPolicy Bypass -File .\install-browser.ps1
```

Clicks, typing and screenshots remain permission-gated. Browser content is untrusted input.

## Integrations and MCP

```powershell
.\.venv\Scripts\skynet-admin.exe integrations
.\.venv\Scripts\skynet-admin.exe capabilities
.\.venv\Scripts\skynet-admin.exe tools
```

Dynamic MCP tools are confirmation-required by default, risk-classified and included in signed receipts. Integration manifests under `.skynet/integrations.d/*.json` are declarative metadata only and cannot grant themselves authority.

## Channels

Set a private local token in `.env`:

```text
SKYNET_WEBHOOK_TOKEN=<your-random-secret>
SKYNET_CHANNEL_HOST=127.0.0.1
SKYNET_CHANNEL_PORT=8765
```

Launch explicitly:

```powershell
.\.venv\Scripts\skynet-channel.exe
```

Inbound contract:

```text
POST /inbound/<channel>/<peer>?session=<session_id>
Authorization: Bearer <token>
X-SKYNET-Event-ID: <stable-provider-event-id>
{"content":"message","event_id":"optional-alternative-id"}
```

Outbound adapters poll `GET /outbox`. The bridge binds to loopback by default and refuses a remote bind unless explicitly enabled.

## Automations

```powershell
.\.venv\Scripts\skynet-admin.exe automations
.\.venv\Scripts\skynet-admin.exe automation-once 300 <session_id> "check the result and summarize changes"
```

Unattended execution cannot approve confirmation-required actions.

## Install on Windows

Requirements: Windows 10/11, Python 3.11+, Git and Ollama.

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

Core / admin / evolution / trust / simulation:

```powershell
.\.venv\Scripts\skynet.exe
.\.venv\Scripts\skynet-admin.exe status
.\.venv\Scripts\skynet-evolve.exe status
.\.venv\Scripts\skynet-trust.exe status
.\.venv\Scripts\skynet-sim.exe report
```

Supervisor:

```powershell
.\.venv\Scripts\skynet-supervisor.exe
```

## Emergency control

```powershell
powershell -ExecutionPolicy Bypass -File .\emergency-stop.ps1
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
10. Historical and synthetic failures become regression material instead of being forgotten.
11. Improvement promotion remains measured, canary-based and rollback-capable.
12. Synthetic operational time is evidence, never a substitute for real field validation.

## Next gate: real-PC benchmark

V0.10 deliberately compresses pre-field experience. The next evidence gate is still a **Reality Benchmark on the target Windows PC**, measuring task success, intervention rate, false-success rate, recovery, steps, latency, resource pressure and permission fatigue.

Synthetic failures discovered before or after that benchmark feed back into the accelerator and regression suites, so the test corpus grows with every real mistake.
