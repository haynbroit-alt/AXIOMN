# AXIOMN — Target Levels & Roadmap

The target, set by the project owner, is five stars in every dimension:

| Niveau | Vision cible |
|---|---|
| Vision | ⭐⭐⭐⭐⭐ |
| Architecture | ⭐⭐⭐⭐⭐ |
| Code | ⭐⭐⭐⭐⭐ |
| Infrastructure | ⭐⭐⭐⭐⭐ |
| Produit | ⭐⭐⭐⭐⭐ |
| Traction | ⭐⭐⭐⭐⭐ |

This document is the honest gap analysis: where each dimension stands
today, what five stars actually means for it, and the concrete steps
between the two. Ratings are deliberately harsh — a roadmap that flatters
the current state is useless for closing the gap.

## What AXIOMN is, long-term

> AXIOMN is an open-source **intent mediation runtime**: it transforms a
> human intent into a graph of executable actions, independently of the
> AI model, the operating system, or the service provider behind it.

Not an assistant, not an app — a runtime other software builds on. That
framing drives the trajectory below: the projects that became universal
layers (Linux, Git, Kubernetes, LLVM, Python) didn't start by selling a
product; they became a platform others built on, and adoption came from
the builders. AXIOMN's endgame is the same: traction should eventually
come from applications that *embed* AXIOMN, not only from an app named
AXIOMN.

```
Vision → Kernel → Infrastructure → Capabilities → Product → Platform → Ecosystem → Adoption
```

| Stage | What it means for AXIOMN | Status |
|---|---|---|
| Kernel | The `Intent → Route → Execute → Act` pipeline and its contracts | ✅ started (this repo) |
| Infrastructure | CI, auth, persistence, deployment, observability | 🔄 tier 1 in PR #5 |
| Capabilities | Real backends behind the contracts: a real LLM, a real human queue, real tools | ❌ stubs today |
| Product | A reference client (web demo, mobile) proving the runtime end-to-end | 🔄 exists, unproven |
| Platform | A stable, versioned API + SDK that third parties can depend on | 🔄 SDK started, API unversioned |
| Ecosystem | Plugins: community-contributed classifiers, tools, route profiles, action types | ❌ not started |
| Adoption | Third-party applications embedding AXIOMN as their routing layer | ❌ not started |

## Summary

| Dimension | Today | Target | The gap in one sentence |
|---|---|---|---|
| Vision | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | Clear and documented, but lives only in the README — no positioning vs. Siri/Rabbit/agents, no "why now". |
| Architecture | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | Clean pluggable contracts with a real feedback loop, but synchronous-only and never proven under real load. |
| Code | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | Small, fully tested, typed dataclasses everywhere — but no enforced type checking or coverage gate. |
| Infrastructure | ⭐⭐ | ⭐⭐⭐⭐⭐ | Until PR #5 lands: no CI, no auth, no persistence; after it: still no deployment, observability, or real database. |
| Produit | ⭐⭐ | ⭐⭐⭐⭐⭐ | The pipeline is real but the answers aren't: `cloud_ai` returns a template string, the human queue is a stub, the Android app has never been built. |
| Traction | ⭐ | ⭐⭐⭐⭐⭐ | Zero users. Nothing in this repo can change that directly; it can only remove the blockers (a real answer engine, a deployable service, usage telemetry). |

## Vision — ⭐⭐⭐⭐ → ⭐⭐⭐⭐⭐

**Today.** The core idea — a universal intent mediation layer that decides
*how* a request should be answered rather than being the answer — is
crisp, differentiated, and already written down (README intro, the
"deliberately out of scope" section). The architecture visibly serves the
vision instead of contradicting it.

**What ⭐⭐⭐⭐⭐ means.** The vision survives contact with a skeptic. A
canonical document that states: the problem (every assistant is a silo
that answers everything itself, badly), why mediation beats monolith
(cost, privacy, quality, and the ability to say "a human should take
this"), why now (on-device models finally make the local route real),
who it's for first, and what the moat is (the routing feedback loop —
trust scores learned from real outcomes — compounds with usage; the
models being routed to don't).

**Path.**
1. ~~Write `VISION.md`: problem, thesis, why-now, wedge, moat, explicit
   non-goals~~ — ✅ done, including the four invariants (intent as
   single entry point, interchangeable capabilities, user-owned data,
   observability/explainability) with an honest note on where the code
   does and doesn't honor each one yet.
2. Add a competitive positioning section: what Siri/Assistant, LLM
   chat apps, and agent frameworks each get wrong that mediation fixes.
3. ~~Name the sequencing: SDK-first before consumer-assistant~~ — ✅
   done ("The wedge and the sequencing" in `VISION.md`).

## Architecture — ⭐⭐⭐⭐ → ⭐⭐⭐⭐⭐

**Today.** Four small layers with narrow, swappable contracts
(`IntentClassifier`, `RouteProfile`, `ToolHandler`, `ActionEngine`), a
router that scores on capability/cost/latency/trust/ambiguity instead of
fixed thresholds, and a closed feedback loop (`record_outcome`) so routing
learns from real results. Every layer is independently testable and is.

**What ⭐⭐⭐⭐⭐ means.** The same contracts, proven beyond a single
synchronous process: requests that outlive an HTTP call (the human queue
is inherently async — today `await_human` is a signal with no delivery
mechanism behind it), streaming results, per-user routing state, and
evidence the router's scoring actually beats a naive baseline.

**Path.**
1. Async escalation: a request queued to `human_queue` gets an ID; a
   client can poll or subscribe for the eventual answer. This is the
   single biggest architectural gap — `await_human` currently promises
   something the system can't deliver.
2. Streaming: `ExecutionEngine` supports incremental results for the
   cloud route (token streaming), with the Action Engine deciding once
   the stream ends.
3. Per-tenant router state: trust scores and outcomes keyed by API key,
   not global.
4. A routing-quality benchmark: a fixed corpus of labeled requests, with
   the scored router measured against a difficulty-threshold baseline —
   turning "dynamic routing is better" from a claim into a number.

## Code — ⭐⭐⭐⭐ → ⭐⭐⭐⭐⭐

**Today.** ~800 lines of Python, 44+ tests that exercise real behavior
(the SDK tests run against a live loopback server, the web demo was
driven by a real browser), dataclasses with type hints throughout, and
lint (`ruff`) coming in PR #5. The codebase is small enough to hold in
your head — that's a feature.

**What ⭐⭐⭐⭐⭐ means.** Nothing relies on discipline: types, coverage,
and style are all enforced by machines, and a new contributor can't
accidentally regress them.

**Path.**
1. `mypy --strict` (or pyright) clean, enforced in CI.
2. A coverage floor in CI (the suite is thorough; make that measurable
   and protected).
3. Docstrings on every public contract (`IntentClassifier`,
   `ToolHandler`, `RouteProfile`, `ActionEngine.decide`) — they are the
   extension API and should read like one.
4. Property-based tests (hypothesis) for the router's scoring
   invariants, e.g. "CONNECT always escalates to a human" holds for all
   inputs, not just the sampled ones.

## Infrastructure — ⭐⭐ → ⭐⭐⭐⭐⭐

**Today.** Honestly the weakest engineering dimension. On `main`: no CI,
no auth, no rate limiting, no persistence — every restart forgets
everything. PR #5 (open) closes the first tier: GitHub Actions running
lint + the full suite, opt-in API keys and rate limiting, and JSON-file
persistence for router trust scores.

**What ⭐⭐⭐⭐⭐ means.** Someone who isn't the author can deploy AXIOMN,
watch it run, and trust it: one-command deployment, real storage,
observability, and secrets handled properly.

**Path.**
1. Land PR #5 (CI, auth, rate limiting, trust-score persistence).
2. `Dockerfile` + compose file; a tagged image published from CI.
3. Structured logging (request ID, intent, route, tool, latency) and a
   `/metrics` endpoint — this doubles as the foundation for measuring
   traction.
4. Replace JSON-file state with SQLite (still zero-ops) behind a storage
   interface, so Postgres is a config change, not a rewrite.
5. A deployed reference instance (Fly.io/Railway/VPS) with a health
   check, so the demo has a URL instead of a `git clone`.

## Produit — ⭐⭐ → ⭐⭐⭐⭐⭐

**Today.** The pipeline is real end-to-end, and the `/ui/` demo showing
*how* each answer was produced (intent, route, tool, confidence, timing)
is genuinely the product's identity. But the answers themselves aren't
real: `cloud_ai` returns a template string, not an LLM response; the
human queue accepts requests no human will ever see; the Android client
has never been compiled (no Android SDK in the dev environment).

**What ⭐⭐⭐⭐⭐ means.** A person with a real question gets a real answer,
on the device they actually carry, and prefers this over opening a chat
app — because easy things resolve instantly and locally, hard things get
a visibly better answer, and impossible things reach a human instead of
being hallucinated.

**Path.**
1. **Real LLM behind `cloud_ai`** — the single highest-leverage change
   in the entire roadmap. The `ToolHandler` contract already fits; it
   needs an API key from the repo owner and a thin client. Everything
   downstream (product feel, demo credibility, traction) is blocked on
   answers being real.
2. A minimal real human queue: even "forward to a Telegram/Discord
   channel, post the reply back" makes `await_human` honest.
3. Build and verify the Android app on a real device; fix what the
   compiler and the round-trip reveal.
4. Voice on the web demo (the browser's speech APIs) so the "any
   modality" claim is demonstrable without installing an APK.

## Traction — ⭐ → ⭐⭐⭐⭐⭐

**Today.** Zero users, zero deployments, zero external feedback. One
star is the floor and it's the honest score.

**What ⭐⭐⭐⭐⭐ means.** Not (only) end users of an AXIOMN app —
**developers who embed AXIOMN**. Five-star traction is third-party
applications using AXIOMN as their intent-routing layer, a plugin
ecosystem contributing classifiers/tools/route profiles, and the
router's learned trust scores reflecting *their* production outcomes,
not test fixtures. At that point traction no longer depends on one
application: it compounds through the ecosystem.

**Path.** Code can't create traction, but it removes the blockers, in
order: real answers (Produit #1) → a public deployed instance
(Infrastructure #5) → usage telemetry (Infrastructure #3) → then the
platform steps that make third-party adoption possible rather than just
hoped for:
1. **API stability**: version the `/intent` schema and the SDK, publish
   `axiomn_sdk` to PyPI, document the compatibility promise.
2. **Extensibility as a feature**: entry-point-based plugin discovery so
   a classifier, tool, or action type can be `pip install`ed into a
   running AXIOMN without forking it.
3. **A reason to integrate**: the routing-transparency angle ("watch the
   system decide who should answer you") pitched to builders who need
   routing, not another chatbot — demo URL, writeup, example
   integrations.

## The quality bar

Cross-cutting targets, held to the standard of mature infrastructure
projects. The principle: **don't aim to be the biggest project, aim to
be the most rigorous one** — reliability and coherence are what let
Linux, Git, and Kubernetes become huge. Working method and PR rules are
in [`CONTRIBUTING.md`](CONTRIBUTING.md).

| Area | Target | Today |
|---|---|---|
| Code quality | Coverage > 90% enforced in CI, `mypy --strict` clean, systematic code review | Tests thorough but coverage unmeasured; typed but unenforced; review practiced (PR #4 precedent) but not enforced by branch protection |
| Architecture | Stable interfaces, independent components, versioned API | Contracts stable and independently tested; API unversioned |
| Performance | Low latency, bounded memory, local execution whenever pertinent | Local route ~instant; never measured under load; no memory profile |
| Security | Encryption in transit, authentication, secrets management, dependency audit | Auth + rate limiting opt-in in PR #5; no TLS story, no secrets policy, no dependency audit in CI |
| Documentation | Complete, maintained, accessible: vision, architecture, roadmap, dev + API docs, contribution guides | `VISION.md`, `ARCHITECTURE.md`, `ROADMAP.md`, `CONTRIBUTING.md`, per-module READMEs exist; API docs auto-generated at `/docs`; kept honest in PRs |
| Ecosystem | Official SDKs, plugins, examples, contribution guides | Python SDK exists (unpublished); no plugin mechanism yet |
| Reliability | CI/CD, monitoring, alerting, availability objectives | CI arrives in PR #5; no CD, monitoring, or SLOs |

Metrics to collect once telemetry lands (Infrastructure #3), so
decisions rest on data instead of assumption: response time per route,
routing precision (chosen route vs. best-known outcome), execution cost,
memory footprint, and user satisfaction signals.

## Order of operations

The dependencies above collapse into one sequence, which is the
`Kernel → … → Adoption` trajectory made concrete:

1. Land PR #5 (**Infrastructure** tier 1: CI, auth, persistence).
2. Real LLM behind `cloud_ai` (**Capabilities**) — unblocks Produit and
   everything after.
3. Docker + deployed instance + telemetry (**Infrastructure** tier 2).
4. Async human queue (**Capabilities**; makes `await_human` honest).
5. Verified Android build; voice on the web demo (**Product**).
6. Versioned API + published SDK (**Platform**).
7. Plugin discovery for classifiers/tools/actions (**Ecosystem**).
8. Third-party integrations and the public push (**Adoption**) — only
   after the demo answers real questions.

Vision (`VISION.md`) and Code hardening (mypy, coverage gate) are
parallel tracks with no dependencies; they can start any time.
