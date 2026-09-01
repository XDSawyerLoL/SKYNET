# SKYNET

**Sovereign local-first personal AI for Windows.**

SKYNET is not a wrapper around one cloud model. The project owns the agent core and treats models, runtimes and connectors as replaceable components.

Current milestone: **V0.2**

## Principles

- Local-first and offline-capable.
- No paid API required.
- Persistent local memory.
- Interchangeable local LLMs through Ollama.
- Explicit permissions for consequential actions.
- Windows accessibility before blind visual clicking.
- Optional local vision fallback.
- MCP as an interchangeable tool protocol.
- Reusable learned skills stored locally.
- Structured plans and verification evidence.
- Audit trail.
- External components must remain replaceable.

## V0.2 capabilities

- Local Ollama chat + native tool calling.
- SQLite persistent memory.
- Workspace file read/write.
- Permission-gated PowerShell.
- Windows visible-window discovery.
- Windows UI Automation accessibility snapshots.
- Permission-gated focus / invoke / type actions.
- Screenshot capture inside the workspace.
- Optional Ollama multimodal screenshot analysis.
- Dependency-free MCP stdio client.
- Local MCP server registry.
- Persistent Markdown skills.
- Structured task plans with step evidence.
- SHA-256 chained local audit log.

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
.\.venv\Scripts\skynet.exe
```

Optional local vision model:

```powershell
ollama pull qwen2.5vl:7b
Copy-Item .env.example .env
```

Then set:

```text
SKYNET_VISION_MODEL=qwen2.5vl:7b
```

The vision model is optional. Windows accessibility inspection works without it.

## Useful commands

```text
:status
:memory
:skills
:mcp
:windows
:quit
```

## Security model

Read-only inspection is generally allowed automatically. Actions that modify files, type into applications, invoke UI controls, run PowerShell, capture the screen, save skills or call arbitrary MCP tools require confirmation by default.

Unknown tools are blocked by default.

SKYNET never treats tool/file/web/MCP content as trusted instructions and should never claim success without tool evidence.

See `SECURITY.md` and `docs/V0.2.md`.

## Architecture direction

```text
                    SKYNET CORE
                        |
       +----------------+----------------+
       |                |                |
     Memory           Planner          Skills
       |                |                |
       +---------- Permission/Audit ------+
                        |
                     Tool Bus
          +-------------+-------------+
          |             |             |
       Windows         MCP          Files/Shell
          |
   Accessibility Tree
          |
   deterministic action
          |
     Vision fallback
                        |
                   Model Layer
                        |
              Ollama / future runtimes
```

The long-term goal is a sovereign personal AI whose identity, memory, skills, permissions and operational history survive model changes.

## License

No license has been granted yet. Until a project license is explicitly added, copyright remains with the repository owner.
