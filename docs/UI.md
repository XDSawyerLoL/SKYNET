# SKYNET Desktop UX

The desktop UI intentionally follows a **conversation-first** product rule.

SKYNET may have a complex governed agent core, but that complexity must not be permanently exposed to the user. The default interface should feel closer to a refined conversational assistant than to a monitoring cockpit.

## Design rule

**80% calm assistant / 20% futuristic identity.**

The futuristic character comes from restrained motion, depth, typography and the SKYNET status orb — not from filling the screen with gauges.

## Default layout

- **Left rail:** new conversation, five primary destinations, recent sessions.
- **Center:** conversation and command composer.
- **Top:** current session plus one concise SKYNET status indicator.
- **Right:** context drawer, hidden by default.
- **Identity:** a lightweight animated orb that communicates idle / thinking / acting / stopped states.

Primary destinations:

1. Chat
2. Memory
3. Automations
4. Tools
5. Settings

Advanced information such as receipts, policy details, evolution telemetry, benchmarks, security diagnostics and developer internals remains available through contextual/advanced views and dedicated CLI consoles. It should not dominate the everyday surface.

## Contextual disclosure

The right drawer only opens when useful. Examples:

- Memory shows a concise view of durable memories.
- Automations shows configured routines and creation/run controls.
- Tools summarizes browser, integrations, exposed tools and approved skills.
- Settings summarizes the active model, local paths, autonomy state and kill-switch.
- Search results and advanced system status reuse the same drawer.

## Orb language

The orb is intentionally simple and dependency-free.

- **Idle:** slow cyan breathing.
- **Thinking:** faster cyan pulse.
- **Acting/autonomy:** amber motion.
- **Global stop:** red.

It should communicate that SKYNET is present without creating constant visual distraction or GPU overhead.

## Explicitly removed from the default home surface

The main screen does **not** permanently show:

- CPU/GPU/RAM charts;
- token rate;
- uptime/request counters;
- receipt lists;
- audit-chain visualizations;
- risk-budget graphs;
- skill statistics;
- swarm graphs;
- benchmark telemetry.

Those remain product capabilities, not default UX furniture.

## Implementation constraint

V0.10 keeps the desktop shell on Python/Tk so core installation remains dependency-light and local-first. The new shell uses custom Tk styling and Canvas animation rather than adding a heavyweight browser framework merely for appearance.

If later live-PC evaluation proves that native Tk rendering limits polish materially, the view layer can be replaced while keeping the same Runtime and UX contract. The agent core must not depend on the presentation technology.
