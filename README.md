# SKYNET

**Sovereign local-first governed personal AI for Windows.**

SKYNET owns the agent core and treats models, runtimes, connectors, payment rails and external authorization systems as replaceable adapters. No paid API is required for the default setup.

Current milestone: **V0.5 — Measured Evolution**

## What V0.5 adds

- Objective local benchmark suite for configured Ollama models.
- Scorecards persisted locally in SQLite.
- Promotion only when a candidate beats the baseline without pass-rate or safety regression.
- Deterministic canary routing for a bounded percentage of real prompts.
- Explicit canary acceptance before a candidate becomes preferred.
- Atomic local rollback to the previous model deployment.
- Trajectory mining for repeated successful task patterns.
- Signed, time-bounded capability leases for delegated agents.
- Capability call budgets, expiry, revocation and mandate binding.
- Desktop evolution status plus CLI evolution controls.

V0.5 builds on V0.4:

- Canonical SKYNET Mandate.
- Deterministic Policy Engine.
- Independent PermissionGate.
- Signed SHA-256 hash-chained receipts.
- ERC-8196 / AP2 / OAuth policy projections.
- Parallel bounded local swarms.
- Semantic local memory.
- Persistent success/failure trajectories.
- A2A-ready agent cards and task envelopes.
- Windows UI Automation + optional local vision.
- MCP, skills, routines, checkpoints and multi-model Ollama routing.

## Core doctrine

```text
User Intent
    ↓
Agent reasoning
    ↓
Action proposal
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
    ↓
Trajectory
    ↓
Evaluation
    ↓
Candidate improvement
    ↓
Objective benchmark
    ↓
Canary
    ↓
Accept OR Rollback
```

The model may propose actions and improvements. It cannot approve its own permissions or promote itself without measured evidence and explicit promotion boundaries.

## Sovereignty rules

1. Models are replaceable.
2. Memory, trajectories, skills, policies, receipts, scorecards and deployment state stay local by default.
3. No cloud API is required for core operation.
4. Every tool call crosses deterministic policy enforcement.
5. Sensitive tools remain independently permission-gated.
6. Unattended execution cannot grant itself extra permissions.
7. Learned procedures remain candidates until validated/promoted.
8. External protocols remain adapters, never SKYNET's source of truth.
9. A new model must beat the baseline before canary promotion.
10. A canary can always be rolled back locally.

## Measured model evolution

Configure more than one installed Ollama model:

```text
SKYNET_MODEL=qwen3:8b
SKYNET_MODELS=qwen3:8b,qwen2.5-coder:7b
```

Run:

```text
:tournament
```

SKYNET runs the same deterministic local evaluation suite across configured models. No external LLM judge is required.

If an alternate candidate exceeds the baseline threshold with no safety/pass-rate regression, SKYNET can offer a **20% deterministic canary**. The same prompt always lands in the same canary bucket.

```text
:tournament
:deployments
:accept-canary
:rollback-model
:scorecards
```

A deployment lifecycle is:

```text
baseline
   ↓
objective benchmark
   ↓
measured candidate
   ↓
20% canary
   ↓
observe
  ↙   ↘
accept rollback
   ↓      ↓
preferred previous
```

## Trajectory learning

Every successful or failed agent task can become local evidence.

```text
trajectory
   ↓
reward/outcome
   ↓
repeated successful pattern
   ↓
learning proposal
   ↓
future skill/model adaptation candidate
```

Use:

```text
:trajectories
:learning-proposals
```

V0.5 **does not silently fine-tune itself**. Training adapters/LoRAs remains a future isolated step that must be benchmarked and rollback-capable.

## Delegated agent capability leases

Future A2A-style agents should not inherit SKYNET's authority. V0.5 can issue a signed local lease containing:

- target agent identity;
- exact delegated capabilities;
- current mandate hash;
- expiration;
- maximum call budget;
- local signature;
- revocation state.

Use:

```text
:leases
:lease-issue
```

This primitive can later be adapted to A2A credentials, OAuth delegation or wallet-policy systems without replacing SKYNET's local authorization model.

## Policy adapters

```text
SKYNET Mandate
     │
     ├── ERC-8196 projection
     ├── AP2 constraint projection
     ├── OAuth delegated-scope projection
     └── future adapters (x402 / enterprise policy / others)
```

Use:

```text
:policy
:policy-erc8196
:policy-ap2
:policy-oauth
:receipts
:verify-receipts
```

## Parallel local swarm

```text
Goal
 ├─ planner
 ├─ analyst
 ├─ critic
 ├─ security
 ├─ verifier
 └─ innovator
      ↓
parallel local inference
      ↓
evidence-preserving synthesis
```

Run:

```text
:swarm Analyse ce problème et cherche les faiblesses du plan
```

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

## Optional local embeddings and vision

```text
SKYNET_EMBED_MODEL=nomic-embed-text
SKYNET_VISION_MODEL=qwen2.5vl:7b
```

Without an embedding model, semantic memory falls back to a dependency-free hashed local vectorizer. Windows accessibility remains preferred before vision.

## Main V0.5 CLI commands

```text
:status
:tournament
:scorecards
:learning-proposals
:deployments
:accept-canary
:rollback-model
:leases
:lease-issue
:identity
:policy
:receipts
:verify-receipts
:semantic <query>
:trajectories
:agents
:swarm <goal>
```

Existing memory, skills, routines, checkpoints, MCP and Windows commands remain available.

## Data

Runtime state lives under `.skynet/` by default and is ignored by Git. The workspace is `workspace/` by default.

See `docs/V0.5.md` for the architecture and forward roadmap.
