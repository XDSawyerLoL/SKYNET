# SKYNET

**Sovereign local-first governed personal AI for Windows.**

SKYNET owns the agent core and treats models, runtimes, connectors and external authorization systems as replaceable adapters. No paid API is required for the default setup.

Current milestone: **V0.4 — Sovereign Agent Fabric**

## V0.4 highlights

- Local Ollama chat with automatic routing across configured local models.
- Parallel bounded specialist swarms inspired by modern multi-agent systems.
- Persistent SQLite memory plus semantic retrieval.
- Optional local Ollama embedding model; dependency-free hashed fallback otherwise.
- Persistent trajectory store for successful and failed agent work.
- Restart-safe autonomy checkpoints and local interval routines.
- Windows UI Automation before visual fallback.
- Optional local multimodal vision through Ollama.
- MCP stdio client and local MCP registry.
- A2A-ready local agent cards and delegated task envelopes.
- Learned skills use candidate -> validation -> explicit promotion.
- Deterministic canonical Mandate before tool execution.
- Independent PermissionGate remains a second enforcement layer.
- Signed, SHA-256 hash-chained action receipts.
- Deterministic projections for ERC-8196, AP2-style constraints and delegated OAuth scopes.
- CLI, Desktop and autonomy worker share the same runtime.

## Core execution doctrine

```text
User intent
   ↓
Agent reasoning / planning
   ↓
Action proposal
   ↓
Canonical SKYNET Mandate
   ↓
Deterministic Policy Engine
   ↓
Existing PermissionGate
   ↓
Tool / Windows / MCP execution
   ↓
Evidence + signed hash-chained Receipt
```

The LLM can propose an action. It cannot approve its own action.

## Sovereignty rules

1. Models are replaceable.
2. Memory, trajectories, skills, plans, routines, policies and receipts stay local by default.
3. No cloud API is required for core operation.
4. Every tool call crosses deterministic policy enforcement.
5. Sensitive tools remain permission-gated independently of the policy layer.
6. Unattended execution cannot silently grant itself extra permissions.
7. Learned procedures do not become trusted skills until validated and promoted.
8. External standards are adapters, never the internal source of truth.

## External policy adapters

SKYNET keeps one canonical local mandate and can project it toward external enforcement systems.

```text
SKYNET Mandate
     │
     ├── ERC-8196 projection
     ├── AP2 constraint projection
     ├── OAuth delegated-scope projection
     └── future policy adapters
```

These projections do **not** make SKYNET dependent on Ethereum, AP2 or any identity provider.

## Parallel swarm model

The default swarm stays deliberately bounded rather than spawning dozens of agents blindly:

```text
Goal
 ├─ planner
 ├─ analyst
 ├─ critic
 ├─ security
 └─ verifier
      ↓
parallel local inference
      ↓
evidence-preserving synthesis
```

More roles can be added, with a hard local worker cap.

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

### Launch Desktop

```powershell
powershell -ExecutionPolicy Bypass -File .\launch.ps1
```

### Launch CLI

```powershell
.\.venv\Scripts\skynet.exe
```

### Launch autonomy worker

```powershell
.\.venv\Scripts\skynet-worker.exe
```

The worker may perform read-only/SAFE work unattended. Confirmation-gated actions remain denied until the user is present.

## Multi-model routing

```text
SKYNET_MODEL=qwen3:8b
SKYNET_MODELS=qwen3:8b,qwen2.5-coder:7b
```

SKYNET chooses from installed candidates and falls back to the default model if a specialist fails.

## Optional local semantic embeddings

Without configuration, semantic memory uses a dependency-free hashed local vector fallback.

For higher-quality semantic retrieval, install a local Ollama embedding model and set it in `.env`, for example:

```text
SKYNET_EMBED_MODEL=nomic-embed-text
```

## Optional local vision

```text
SKYNET_VISION_MODEL=qwen2.5vl:7b
```

Windows accessibility inspection remains the preferred path before vision.

## V0.4 governance CLI

```text
:identity
:policy
:policy-erc8196
:policy-ap2
:policy-oauth
:receipts
:verify-receipts
:semantic <query>
:trajectories
:agents
:swarm <goal>
```

Existing memory, skill, routine, checkpoint, MCP and Windows commands remain available.

## Learned knowledge lifecycle

```text
successful or failed trajectory
          ↓
local evidence store
          ↓
repeatable procedure identified
          ↓
skill candidate
          ↓
validation
          ↓
explicit promotion
          ↓
approved reusable skill
```

V0.4 records trajectories but does not silently fine-tune itself. Future model adaptation must remain separately evaluated, versioned and rollback-capable.

## Interoperability direction

- **MCP**: agent-to-tool integration.
- **A2A**: future agent-to-agent interoperability.
- **AP2 / ERC-8196 / OAuth-style delegation**: external policy enforcement adapters.
- **x402 and future payment rails**: optional execution adapters behind the same canonical mandate boundary.

SKYNET's internal identity, memory and policy model remain stable even if any external protocol changes.

## Data

Runtime state lives under `.skynet/` by default and is ignored by Git. The workspace is `workspace/` by default.

See `docs/V0.4.md` for the architecture and forward roadmap.
