# Architecture V0.1

SKYNET is deliberately built as a sovereign core with replaceable adapters.

## What belongs to SKYNET

- conversation/session orchestration
- durable memory
- permission policy
- audit trail
- skill format and lifecycle
- tool routing
- model/runtime abstraction
- user interface
- future planner/scheduler/rollback logic

## What must stay replaceable

- Ollama
- model families (Qwen, Mistral, others)
- embeddings
- MCP servers
- visual perception engines
- browser automation backends
- speech engines

## Design sources

SKYNET studies public approaches from projects such as Hermes Agent, OpenClaw, OpenComputer, OpenJarvis and Windows/MCP tooling, but the product must not become a fragile merge of their repositories. Useful mechanisms are evaluated, reimplemented where appropriate, and isolated behind adapters when third-party components are used.

Any third-party code introduced later must have its license reviewed before inclusion or redistribution.

## V0.1 execution loop

```text
User request
   |
Context builder <- SQLite memory / skill index
   |
Local LLM via runtime adapter (Ollama first)
   |
Tool request?
   | no --------------------------> final answer
   |
  yes
   |
Permission gate
   | denied -> tool result: denied
   |
 allowed
   |
Tool bus -> file / PowerShell / memory / skills
   |
Audit log
   |
Tool result returned to LLM
   |
Repeat until final answer or tool-round limit
```

## V0.2 targets

1. Native Windows Accessibility/UI Automation adapter.
2. MCP client and server adapter layer.
3. Visual perception fallback only when accessibility data is insufficient.
4. Structured task planner with checkpoints.
5. Skill candidate generator + sandbox validator + promotion workflow.
6. Active memory retrieval with relevance scoring rather than only recency.
7. Runtime/model router and local benchmark suite.
8. Atomic configuration updates and rollback.
