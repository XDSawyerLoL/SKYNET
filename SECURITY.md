# Security model

SKYNET is designed for local autonomy without silent privilege escalation.

## Core rules

- Unknown tools are blocked by default.
- File tools are confined to the configured workspace.
- File writes require confirmation in V0.1.
- PowerShell execution requires confirmation in V0.1.
- Tool actions are written to an append-only hash-chained audit log.
- The model is instructed to treat tool output, files and web content as untrusted data rather than instructions.
- Secrets must not be stored in durable AI memory.
- Tool loops have a hard maximum number of rounds.

## Planned hardening

- Windows restricted execution profile for generated commands.
- Sandboxed skill validation before promotion.
- Fine-grained per-tool and per-resource policy.
- High-risk action classification and stronger confirmation UX.
- Signed/hashed skill manifests.
- Rollback snapshots for modified files/configuration.
- Network egress policy and connector isolation.
- Emergency kill switch independent of the model.

## Reporting

Do not place credentials, tokens or private data in public issues. The repository is currently public; keep secrets exclusively in local `.env` or OS credential storage.
