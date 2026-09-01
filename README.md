# SKYNET

**Sovereign local-first personal AI for Windows.**

SKYNET owns the agent core and treats models, runtimes and connectors as replaceable components. No paid API is required for the default setup.

Current milestone: **V0.3**

## V0.3 highlights

- Local Ollama chat with automatic routing across configured local models.
- Persistent SQLite memory.
- Restart-safe autonomy checkpoints.
- Local interval routines persisted in SQLite.
- Unattended routines never auto-approve consequential actions.
- Windows UI Automation before visual fallback.
- Optional local multimodal vision through Ollama.
- MCP stdio client and local MCP server registry.
- Learned skills now enter a candidate state first.
- Skill validation + explicit promotion before a skill becomes active.
- Structured execution plans with evidence.
- SHA-256 chained audit log.
- Three frontends using the same runtime: CLI, Desktop and autonomy worker.

## Sovereignty rules

1. The model is replaceable.
2. Memory, skills, plans, routines and audit data stay local by default.
3. No cloud API is required for core operation.
4. Sensitive tools remain permission-gated.
5. Unattended execution cannot silently grant itself extra permissions.
6. Learned procedures do not become trusted skills until validated and promoted.

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

### Launch the desktop app

```powershell
powershell -ExecutionPolicy Bypass -File .\launch.ps1
```

Or directly:

```powershell
.\.venv\Scripts\skynet-desktop.exe
```

### Launch the terminal UI

```powershell
.\.venv\Scripts\skynet.exe
```

### Launch the autonomy worker

```powershell
.\.venv\Scripts\skynet-worker.exe
```

The worker checks due routines at the configured polling interval. It can use read-only/SAFE tools, but confirmation-gated actions are denied while unattended and reported back as requiring user approval.

## Multi-model local routing

The default setup uses one model:

```text
SKYNET_MODEL=qwen3:8b
SKYNET_MODELS=qwen3:8b
```

You can add installed local specialists without changing the agent core, for example:

```text
SKYNET_MODEL=qwen3:8b
SKYNET_MODELS=qwen3:8b,qwen2.5-coder:7b
```

SKYNET chooses among installed candidates and falls back to the default model if a specialist fails.

## Optional local vision

```powershell
ollama pull qwen2.5vl:7b
Copy-Item .env.example .env
```

Then set:

```text
SKYNET_VISION_MODEL=qwen2.5vl:7b
```

Windows accessibility inspection still works without a vision model.

## CLI commands

```text
:status
:memory
:skills
:skill-candidates
:skill-validate <name>
:skill-promote <name>
:routines
:routine-add
:routine-run
:checkpoints
:mcp
:windows
:quit
```

## Learned skill lifecycle

```text
successful procedure
      ↓
skill candidate
      ↓
static quality/safety validation
      ↓
explicit user-approved promotion
      ↓
approved reusable skill
```

A skill is documentation/procedure. It does not rewrite the SKYNET core.

## Autonomy model

```text
routine due
   ↓
checkpoint: running
   ↓
agent executes local SAFE/read-only work
   ↓
consequential tool requested?
   ├─ no  → continue + verify
   └─ yes → deny unattended action + report approval needed
   ↓
checkpoint: ok / needs_user / failed
   ↓
next run scheduled
```

## Data

Runtime state lives under `.skynet/` by default and is ignored by Git. The workspace is `workspace/` by default.

See `docs/V0.3.md` for the architecture and milestone details.
