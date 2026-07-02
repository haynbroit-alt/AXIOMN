# AXIOMN — Architecture

This document describes the layer stack, the contracts between layers,
and the rules that keep the architecture stable while features are
added. The invariants these rules serve are in [`VISION.md`](VISION.md);
where each layer is headed is in [`ROADMAP.md`](ROADMAP.md).

## The layer stack

```
Ecosystem      third-party plugins: classifiers, tools, route profiles, action types
Integrations   AXIOMN embedded inside other products
Applications   reference clients: /ui/ web demo, android/
SDK            sdk/axiomn_sdk — a thin, dependency-light client of the API
API            axiomn/api — the versioned HTTP surface (POST /intent)
Kernel         axiomn/{intent,router,execution,action,models} — the pipeline itself
```

**The dependency rule: layers depend only downward, and an upper layer
must never force a change in a lower one.** The SDK knows the API
schema, not the kernel. The applications know the SDK/API, not the
router's scoring. A new application, integration, or plugin that
requires editing the kernel means the kernel's contract is wrong — stop
and fix the contract, don't patch through the layers.

Today the bottom four layers exist (Kernel, API, SDK, Applications);
Integrations and Ecosystem are roadmap (see the trajectory in
`ROADMAP.md`).

## The kernel

Four small stages with narrow, swappable contracts:

```
text/voice input
      |
      v
 Intent Engine    -> classify(text) -> Intent
      v               (category, topic, language, difficulty, confidence, ambiguity)
    Router        -> route(intent) -> Route
      v               scores every RouteProfile: capability fit, cost, latency,
      |               trust, category affinity, ambiguity
 Execution Layer  -> execute(route, intent) -> ExecutionOutcome
      v               picks a tool from the ToolRegistry, times it, reports the
      |               outcome back to the Router (the feedback loop)
 Action Engine    -> decide(intent, route, result) -> Action
                      what to DO with the result: voice_reply, copy_to_clipboard,
                      open_url, schedule_task, await_human
```

| Contract | Defined in | Implemented by |
|---|---|---|
| `IntentClassifier` | `axiomn/intent/classifiers.py` | `HeuristicIntentClassifier` (default, offline), `SemanticIntentClassifier` (embeddings, opt-in) |
| `RouteProfile` | `axiomn/router/router.py` | `local_ai`, `cloud_ai`, `human_queue` profiles |
| `ToolHandler` | `axiomn/models/tools.py` | `local_heuristic`, cloud stub, human-queue stub |
| `ActionEngine.decide` | `axiomn/action/engine.py` | category → action policy; `await_human` always wins for `human_queue` |

These four contracts are the extension API. Everything on the roadmap —
a real LLM, a real human queue, streaming, plugins — plugs into one of
them.

## The rules

1. **New modules respect existing interfaces.** A feature is implemented
   behind an existing contract whenever one fits. Adding a capability
   means registering a `ToolHandler`; adding a resolver means a
   `RouteProfile`; adding an input understanding means an
   `IntentClassifier`.

2. **A feature that forces project-wide edits is an architecture
   review, not a big diff.** If implementing something touches more than
   its own layer plus the schema it extends, the contracts are wrong for
   it. The precedent: ambiguity routing (PR #4) was proposed as a router
   rewrite and landed instead as one new term in the existing scoring —
   because a rewrite would have silently dropped existing guarantees.

3. **Guarantees are tests, not intentions.** Every behavioral guarantee
   the architecture makes (e.g. "CONNECT always escalates to a human",
   "`await_human` always wins for `human_queue`", "default ambiguity is
   a strict no-op") exists as a test. Changing a guarantee means
   changing its test, visibly, in review.

4. **Every stage stays independently testable.** Each kernel stage is
   constructible and testable without the API, and the SDK is tested
   against a real loopback server, not mocks of itself.

5. **The explanation travels with the result.** Every stage contributes
   to the response's self-explanation (intent fields, chosen route, tool
   name, timing). A stage that produces an unexplained result violates
   invariant 4 in `VISION.md`.

## Extending AXIOMN (developer guide)

- **New tool/capability**: implement `ToolHandler`, register it in the
  `ToolRegistry` with its route and tags. Nothing else changes.
- **New route**: add a `RouteProfile` with its capability range, cost,
  latency, and weights. The router scores it like any other.
- **New classifier**: implement `IntentClassifier` (return a
  `Classification`: category, confidence, ambiguity) and pass it to
  `IntentEngine`.
- **New action type**: extend the `Action` schema and the
  `ActionEngine.decide` policy — and its tests — together.

## API surface

`POST /intent` is the single functional endpoint (invariant 1: intent is
the single entry point). Interactive API documentation is auto-generated
by FastAPI at `/docs` when the server is running. The response schema is
the contract the SDK and all clients depend on; changing it is a
platform-layer event and, once the API is versioned (see ROADMAP,
Platform stage), a compatibility commitment.
