# SKYNET

**Sovereign local-first governed personal AI for Windows.**

SKYNET owns the agent core and treats models, runtimes, connectors, payment rails and external authorization systems as replaceable adapters. No paid API is required for the default setup.

Current milestone: **V0.8 — Trust & Resilience**

## What V0.8 adds

- Separate **Health Supervisor** process for the autonomy worker.
- Independent worker heartbeat thread, including hung-worker detection.
- Automatic restart after unexpected worker failure.
- **Crash-loop protection**: repeated failures engage the global kill-switch instead of restarting forever.
- Deterministic **global kill-switch below the LLM**, checked before policy/tool execution.
- Desktop **ARRÊT GLOBAL** / explicit re-arm controls.
- Signed, tamper-evident **candidate validation reports** bound to SKYNET's local identity.
- **Failure-derived regression suite** built from real historical failed trajectories; replays are analysis-only and never use tools.
- Verified portable state backup/import with SHA-256 file manifests.
- Full-identity backup protected with **Windows DPAPI** for the same Windows user profile.
- Opt-in Windows startup for the supervisor; SKYNET never installs persistence by itself.

V0.8 keeps the V0.7 Adaptive Lab: Windows Sandbox / WSL2 / static backends, generated candidate skills, local hardware profiling, resource-aware routing, telemetry, Red Team, risk budgeting, immutable baseline, canary/rollback, mandates, receipts, MCP, Windows control, memory and autonomy.

## Trust chain

```text
real task
   ↓
trajectory / evidence
   ↓
candidate
   ↓
Adaptive Lab
   ↓
Red Team
   ↓
historical regressions
   ↓
objective benchmark
   ↓
resource telemetry
   ↓
signed validation report
   ↓
canary
   ↓
accept OR rollback
```

The model may propose an improvement. It cannot grant itself authority, disable the kill-switch, forge a validation report or bypass the policy/permission boundary.

## Global stop

From the Desktop UI, press **ARRÊT GLOBAL**.

Or from PowerShell:

```powershell
powershell -ExecutionPolicy Bypass -File .\emergency-stop.ps1
```

Equivalent CLI:

```powershell
.\.venv\Scripts\skynet-trust.exe kill "manual stop"
```

While engaged, all governed tool calls are denied below the LLM and unattended autonomy stops. Rearm only explicitly:

```powershell
powershell -ExecutionPolicy Bypass -File .\rearm.ps1
```

or:

```powershell
.\.venv\Scripts\skynet-trust.exe rearm
```

## Supervisor and crash recovery

Run the separate supervisor:

```powershell
.\.venv\Scripts\skynet-supervisor.exe
```

The worker sends a heartbeat independently of its current task. If the worker crashes or stops heartbeating, the supervisor can restart it. Persistent routine checkpoints remain the source of restart context. Repeated crashes trip crash-loop protection and engage the global kill-switch.

Opt-in startup:

```powershell
powershell -ExecutionPolicy Bypass -File .\install-startup.ps1
```

Remove it:

```powershell
powershell -ExecutionPolicy Bypass -File .\remove-startup.ps1
```

SKYNET does **not** enable startup automatically during installation.

## Failure-derived regression tests

Historical failed trajectories become side-effect-free regression prompts. The original goal is analyzed with **no tools** and the current model must require verification/evidence rather than falsely claiming historical success.

```powershell
.\.venv\Scripts\skynet-trust.exe regression
```

Or test another installed model:

```powershell
.\.venv\Scripts\skynet-trust.exe regression qwen3:8b
```

## Signed candidate validation

After a candidate has been staged and a baseline/scorecard exists:

```powershell
.\.venv\Scripts\skynet-trust.exe validate-candidate <candidate_name>
```

The report records candidate hash, baseline hash, Red Team result, historical regression result and objective scorecard state, then signs the report with SKYNET's local identity.

Inspect reports:

```powershell
.\.venv\Scripts\skynet-trust.exe reports
.\.venv\Scripts\skynet-trust.exe verify-report <report_id>
```

## Backup / migration

Portable backup, suitable for moving non-secret SKYNET state to another machine:

```powershell
.\.venv\Scripts\skynet-trust.exe backup-portable
```

Portable backups intentionally **exclude `identity.key`**. On another installation, the imported state gets the destination SKYNET identity.

Restore:

```powershell
.\.venv\Scripts\skynet-trust.exe restore-portable <archive.zip>
```

A full backup including identity can be protected with Windows DPAPI:

```powershell
.\.venv\Scripts\skynet-trust.exe backup-protected
```

Restore:

```powershell
.\.venv\Scripts\skynet-trust.exe restore-protected <archive.dpapi>
```

DPAPI protection is deliberately documented as **Windows-user-profile bound**, not as a cross-machine portable encryption format. SKYNET does not invent custom cryptography for portable secret migration.

## Adaptive Lab from V0.7

```powershell
.\.venv\Scripts\skynet-evolve.exe status
.\.venv\Scripts\skynet-evolve.exe hardware
.\.venv\Scripts\skynet-evolve.exe telemetry
.\.venv\Scripts\skynet-evolve.exe lab-backends
.\.venv\Scripts\skynet-evolve.exe generate-candidate
.\.venv\Scripts\skynet-evolve.exe redteam
.\.venv\Scripts\skynet-evolve.exe lora-export
```

Windows Sandbox is the preferred security boundary when available. WSL2 remains a compatibility/development backend, not an equivalent security boundary.

## Governed execution

```text
User Intent
    ↓
Reasoning / planning
    ↓
GLOBAL KILL SWITCH
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
Trajectory / telemetry
```

External standards remain adapters:

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

Desktop:

```powershell
powershell -ExecutionPolicy Bypass -File .\launch.ps1
```

CLI:

```powershell
.\.venv\Scripts\skynet.exe
```

Evolution lab:

```powershell
.\.venv\Scripts\skynet-evolve.exe status
```

Trust/resilience console:

```powershell
.\.venv\Scripts\skynet-trust.exe status
```

## Sovereignty rules

1. Models are replaceable.
2. Memory, trajectories, policies, receipts, telemetry, scorecards and deployment state remain local by default.
3. No cloud API is required for core operation.
4. The LLM never decides whether its own consequential action is authorized.
5. The global kill-switch is enforced beneath model reasoning.
6. Generated improvements remain untrusted until independently evaluated.
7. Historical failures become regression evidence instead of being forgotten.
8. Validation reports are signed by the local SKYNET identity.
9. Crash loops stop autonomy rather than restarting forever.
10. Portable exports exclude the local signing key by default.
11. SKYNET does not invent its own portable encryption scheme.
12. Model/candidate promotion remains measured and rollback-capable.
13. External protocols remain adapters, never SKYNET's sovereign source of truth.

Runtime state lives under `.skynet/` by default. See `docs/V0.8.md` for the milestone architecture.
