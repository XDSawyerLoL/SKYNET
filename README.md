# SKYNET

**Sovereign Personal AI for Windows — local-first, model-agnostic, zero mandatory API cost.**

SKYNET is a personal AI operating layer designed to remain useful even if any single model, cloud provider, runtime, or agent framework disappears.

## Principles

- **Local first** — identity, memory, skills and audit history stay on the user's machine by default.
- **No mandatory paid API** — local models are first-class citizens.
- **Model agnostic** — Ollama is the first runtime, not a permanent dependency.
- **Our core** — memory, planning, permissions, skills, orchestration and UI belong to SKYNET.
- **Replaceable adapters** — models, runtimes, MCP servers, embeddings and vision engines can be swapped.
- **Learn safely** — successful procedures can become reusable skills, but never silently rewrite the protected core.
- **Act, then verify** — computer actions must be checked against their expected result.
- **Permission before risk** — sensitive operations require explicit approval.
- **Auditable** — every tool action is logged.

## V0.1 scope

The first milestone intentionally stays small and testable:

1. Talk to a local LLM through Ollama.
2. Persist conversation memory in SQLite.
3. Keep model/runtime behind an adapter interface.
4. Expose a permission-gated tool bus.
5. Read/write files within an allowed workspace.
6. Run PowerShell commands with explicit confirmation.
7. Store reusable local skills as declarative Markdown files.
8. Record tool actions in an audit log.

The next layers will add Windows Accessibility/UI Automation, MCP, visual fallback, task planning, skill generation/validation, scheduler, notifications and multimodel routing.

## Architecture

```text
                   SKYNET CORE
                       |
        +--------------+---------------+
        |              |               |
     Memory         Skills        Permissions
        |              |               |
        +--------------+---------------+
                       |
                   Tool Bus
             +---------+---------+
             |                   |
          Windows              Files
          Shell/MCP            Workspace
             |
          Perception
      Accessibility -> Vision
             |
         Model Router
             |
     Runtime abstraction
       |       |       |
    Ollama  llama.cpp  future
```

## Quick start

### Requirements

- Windows 10/11
- Python 3.11+
- Ollama installed and running
- A local chat model already pulled in Ollama

### Install

```powershell
git clone https://github.com/XDSawyerLoL/SKYNET.git
cd SKYNET
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e .
```

### Configure

```powershell
Copy-Item .env.example .env
```

Edit `.env` if your Ollama endpoint or model is different.

### Run

```powershell
skynet
```

Or:

```powershell
python -m skynet
```

## Security model

V0.1 uses four conceptual permission levels:

- `observe` — read-only information.
- `safe` — low-risk local actions.
- `confirm` — requires user confirmation.
- `blocked` — unavailable to the agent.

PowerShell execution is `confirm` by default. File writes are restricted to the configured workspace.

## Project status

**V0.1 — foundation under active development.**

The goal is not to clone Hermes, OpenClaw, OpenComputer or OpenJarvis. SKYNET studies the strongest public ideas in the agent ecosystem, then implements a sovereign architecture where external components remain optional and replaceable.
