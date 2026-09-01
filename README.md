# SKYNET

**Sovereign local-first governed personal AI for Windows.**

SKYNET owns the agent core and treats models, runtimes, connectors, payment rails and external authorization systems as replaceable adapters. No paid API is required for the default setup.

Current milestone: **V0.6 — Isolated Evolution**

## What V0.6 adds

- Deterministic **plan-level Risk Budget Engine**.
- Local **Red Team Suite** for self-approval, secret exfiltration, prompt injection and false-success behavior.
- Isolated **Candidate Sandbox** for proposed improvements; V0.6 does not execute candidate core code on the host.
- Local **Adaptation Pipeline** that exports high-reward trajectories as JSONL for future LoRA/adapters.
- Secret/token scrubbing before adaptation data is written.
- Immutable first **baseline manifest** for future model adaptation comparisons.
- Dedicated `skynet-evolve` console, separate from normal chat/autonomy.

V0.6 builds on V0.5:

- objective local model tournaments and scorecards;
- deterministic 20% canary routing;
- accept/rollback model deployments;
- trajectory mining;
- signed time-bounded capability leases;
- canonical Mandates + deterministic Policy Engine + PermissionGate;
- signed hash-chained receipts and ERC-8196/AP2/OAuth projections;
- bounded local swarms, semantic memory, A2A-ready agent cards;
- Windows UI Automation, optional local vision, MCP, skills, routines and checkpoints.

## Evolution doctrine

```text
real task
   ↓
trajectory + evidence
   ↓
repeated successful pattern
   ↓
candidate improvement
   ↓
Candidate Sandbox
   ↓
static checks + Red Team
   ↓
objective benchmark
   ↓
canary
   ↓
accept OR rollback
```

For future model adaptation:

```text
high-reward trajectories
        ↓
secret scrubber
        ↓
local JSONL dataset
        ↓
external/local LoRA trainer (not automatic in V0.6)
        ↓
new model candidate
        ↓
red-team + benchmark + canary + rollback
```

The agent may propose improvements. It cannot silently execute candidate core code, replace the immutable baseline, bypass the Red Team gate, or grant itself new permissions.

## Risk budgeting

SKYNET scores the **whole plan**, not only individual tool calls. High-risk concepts such as credentials, wallet/payment actions, registry changes, elevation, uploads and deletion accumulate risk. The risk engine is deterministic and independent from the LLM.

```powershell
.\.venv\Scripts\skynet-evolve.exe risk-plan <plan_id>
```

Tool execution still separately crosses the canonical Mandate, Policy Engine and PermissionGate.

## Red-team a local model

```powershell
.\.venv\Scripts\skynet-evolve.exe redteam
```

Or test a specific installed Ollama model:

```powershell
.\.venv\Scripts\skynet-evolve.exe redteam qwen3:8b
```

## Immutable adaptation baseline

After generating model scorecards:

```powershell
.\.venv\Scripts\skynet-evolve.exe freeze-baseline
```

The first baseline manifest is preserved. Re-running the command does not silently replace it.

Export a local training dataset from successful trajectories:

```powershell
.\.venv\Scripts\skynet-evolve.exe lora-export
```

The export is preparation only. **V0.6 does not autonomously fine-tune or install a model.**

## Candidate sandbox

```powershell
.\.venv\Scripts\skynet-evolve.exe sandbox-stage candidate-1 skill .\proposal.md
.\.venv\Scripts\skynet-evolve.exe sandbox-list
```

Artifacts are stored under `.skynet/candidate-sandbox/` with SHA-256 manifests and cannot escape that directory through their candidate name.

## Model evolution from V0.5

Configure multiple local models:

```text
SKYNET_MODEL=qwen3:8b
SKYNET_MODELS=qwen3:8b,qwen2.5-coder:7b
```

Inside the main CLI:

```text
:tournament
:deployments
:accept-canary
:rollback-model
:scorecards
:learning-proposals
```

A new model must beat the baseline without safety/pass-rate regression before canary promotion.

## Governed execution

```text
User Intent
    ↓
Reasoning / planning
    ↓
Canonical Mandate
    ↓
Deterministic Policy Engine
    ↓
PermissionGate
    ↓
Execution
    ↓
Evidence + signed Receipt
```

External standards remain adapters, not SKYNET's source of truth:

```text
SKYNET Mandate
 ├─ ERC-8196 projection
 ├─ AP2 projection
 ├─ OAuth delegated scopes
 └─ future x402 / A2A / enterprise adapters
```

## Install on Windows

Requirements: Windows 10/11, Python 3.11+, Git and Ollama.

```powershell
git clone https://github.com/XDSawyerLoL/SKYNET.git
cd SKYNET
powershell -ExecutionPolicy Bypass -File .\install.ps1
ollama pull qwen3:8b
```

Launch Desktop:

```powershell
powershell -ExecutionPolicy Bypass -File .\launch.ps1
```

Launch CLI:

```powershell
.\.venv\Scripts\skynet.exe
```

Launch autonomy worker:

```powershell
.\.venv\Scripts\skynet-worker.exe
```

Evolution/security console:

```powershell
.\.venv\Scripts\skynet-evolve.exe status
```

## Sovereignty rules

1. Models are replaceable.
2. Core memory, trajectories, policies, receipts, scorecards and deployment state remain local by default.
3. No cloud API is required for core operation.
4. The LLM never decides whether its own consequential action is authorized.
5. Improvements are candidates before they become trusted.
6. Candidate core code is not executed directly on the host by V0.6.
7. Adaptation data is scrubbed for common secret/token patterns.
8. A baseline cannot be silently replaced.
9. Model promotion requires measured evidence and remains rollback-capable.
10. External protocols are adapters, never the sovereign internal source of truth.

Runtime data lives under `.skynet/` by default. See `docs/V0.6.md` for the milestone architecture.
