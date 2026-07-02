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
| Infrastructure | CI, auth, persistence, deployment, observability | 🔄 CI (lint + tests + 90% coverage floor + Docker smoke test), opt-in auth/rate limiting, router persistence, Dockerfile/compose all shipped; a public deployed instance remains |
| Capabilities | Real backends behind the contracts: a real LLM, a real human queue, real tools | 🔄 Gateway + Anthropic/OpenAI adapters shipped (contract-tested); real calls need API keys; human queue delivers in-process |
| Product | A reference client (web demo, mobile) proving the runtime end-to-end | 🔄 exists, unproven |
| Platform | A stable, versioned API + SDK that third parties can depend on | 🔄 API versioned (`/v1`), SDK targets it; PyPI publication pending |
| Ecosystem | Plugins: community-contributed classifiers, tools, route profiles, action types | ❌ not started |
| Adoption | Third-party applications embedding AXIOMN as their routing layer | ❌ not started |

## Summary

| Dimension | Today | Target | The gap in one sentence |
|---|---|---|---|
| Vision | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | Clear and documented, but lives only in the README — no positioning vs. Siri/Rabbit/agents, no "why now". |
| Architecture | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | Clean pluggable contracts, a real feedback loop, and async human escalation — but no streaming, no per-tenant state, and never proven under real load. |
| Code | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | Small, fully tested (99% coverage, 90% floor in CI), typed dataclasses everywhere — but type checking not yet machine-enforced. |
| Infrastructure | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ | CI (with coverage floor + Docker smoke test), opt-in auth/rate limiting, router persistence, and Docker are in; still no public deployment, structured logging, or real database. |
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
synchronous process: requests that outlive an HTTP call, streaming
results, per-user routing state, and evidence the router's scoring
actually beats a naive baseline.

**Path.**
1. ~~Async escalation: a request queued to `human_queue` gets an ID; a
   client can poll for the eventual answer~~ — ✅ done: `HumanQueue`
   turns every escalation into a `Ticket`; `await_human` now carries a
   `ticket_id` + `status_url`, clients poll `GET /queue/{id}`, an
   operator answers via `POST /queue/{id}/answer`, and the SDK ships
   `wait_for_human()`. The round trip is covered by tests and was
   verified in a real browser. (Still in-memory/in-process: durable
   storage and a real operator channel are Infrastructure/Produit work.)
2. Streaming: `ExecutionEngine` supports incremental results for the
   cloud route (token streaming), with the Action Engine deciding once
   the stream ends.
3. Per-tenant router state: trust scores and outcomes keyed by API key,
   not global.
4. ~~A routing-quality benchmark~~ — ✅ done
   (`tests/test_routing_benchmark.py`): on a 16-intent labeled corpus,
   the scored router resolves 100% vs 69% for the fixed-threshold
   baseline — the number CI now protects.

## Code — ⭐⭐⭐⭐ → ⭐⭐⭐⭐⭐

**Today.** ~1,300 lines of Python, 107 tests that exercise real behavior
(the SDK tests run against a live loopback server, the web demo was
driven by a real browser, provider adapters are pinned against each
vendor's wire format), 99% coverage with a 90% floor enforced in CI,
and `ruff` lint in CI. The codebase is still small enough to hold in
your head — that's a feature.

**What ⭐⭐⭐⭐⭐ means.** Nothing relies on discipline: types, coverage,
and style are all enforced by machines, and a new contributor can't
accidentally regress them.

**Path.**
1. `mypy --strict` (or pyright) clean, enforced in CI.
2. ~~A coverage floor in CI~~ — ✅ done: 90% enforced
   (`--cov-fail-under=90`), 99% measured.
3. Docstrings on every public contract (`IntentClassifier`,
   `ToolHandler`, `RouteProfile`, `ActionEngine.decide`) — they are the
   extension API and should read like one.
4. Property-based tests (hypothesis) for the router's scoring
   invariants, e.g. "CONNECT always escalates to a human" holds for all
   inputs, not just the sampled ones.

## Infrastructure — ⭐⭐ → ⭐⭐⭐⭐⭐

**Today.** Tier 1 is in: GitHub Actions runs lint, the full suite with
a 90% coverage floor (99% measured), and builds + smoke-tests the Docker
image on every push/PR. Opt-in API keys (`AXIOMN_API_KEYS`) and
rate limiting protect `/v1/intent` and the operator endpoint; JSON-file
persistence (`AXIOMN_ROUTER_STATE_PATH`) keeps router trust scores
across restarts; `Dockerfile` + `compose.yml` make deployment one
command. (This supersedes PR #5, which was written against a pre-v1
`main` and can be closed.)

**What ⭐⭐⭐⭐⭐ means.** Someone who isn't the author can deploy AXIOMN,
watch it run, and trust it: one-command deployment, real storage,
observability, and secrets handled properly.

**Path.**
1. ~~Land CI, auth, rate limiting, trust-score persistence~~ — ✅ done (supersedes PR #5).
2. ~~`Dockerfile` + compose file~~ — ✅ done, built and smoke-tested in CI; a tagged image published from CI remains.
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
human queue now delivers answers end-to-end but no real operator channel
watches it yet; the Android client has never been compiled (no Android
SDK in the dev environment).

**What ⭐⭐⭐⭐⭐ means.** A person with a real question gets a real answer,
on the device they actually carry, and prefers this over opening a chat
app — because easy things resolve instantly and locally, hard things get
a visibly better answer, and impossible things reach a human instead of
being hallucinated.

**Path.**
1. **Real LLM behind `cloud_ai`** — 🔄 the Gateway now sits on the
   cloud route with thin Anthropic and OpenAI adapters
   (`axiomn/gateway/providers.py`), selected per request by
   cost/quality/latency and contract-tested against each vendor's exact
   request/response shape. What remains is the part only the owner can
   provide: real API keys (`ANTHROPIC_API_KEY` / `OPENAI_API_KEY` env
   vars) and a real-call verification. Until then, answers are honestly
   labeled `[simulated:...]`.
2. A real operator channel on the human queue: the ticket mechanism and
   operator API exist (`GET /queue`, `POST /queue/{id}/answer`); what's
   missing is a human actually watching it — even "forward new tickets
   to a Telegram/Discord channel, post the reply back" closes the loop.
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
1. **API stability**: ~~version the `/intent` schema~~ ✅ done — `/v1`
   is the documented contract, bare paths stay as hidden compatibility
   aliases, and the SDK targets `/v1`. Remaining: publish `axiomn_sdk`
   to PyPI and write the compatibility promise down.
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
| Code quality | Coverage > 90% enforced in CI, `mypy --strict` clean, systematic code review | Coverage 99%, floor 90% enforced in CI; typed but mypy unenforced; review practiced but not enforced by branch protection |
| Architecture | Stable interfaces, independent components, versioned API | Contracts stable and independently tested; API versioned (`/v1` + hidden aliases) |
| Performance | Low latency, bounded memory, local execution whenever pertinent | Local route ~instant; never measured under load; no memory profile |
| Security | Encryption in transit, authentication, secrets management, dependency audit | Auth + rate limiting shipped (opt-in); secrets only via env vars; no TLS termination story, no dependency audit in CI |
| Documentation | Complete, maintained, accessible: vision, architecture, roadmap, dev + API docs, contribution guides | `VISION.md`, `ARCHITECTURE.md`, `ROADMAP.md`, `CONTRIBUTING.md`, per-module READMEs exist; API docs auto-generated at `/docs`; kept honest in PRs |
| Ecosystem | Official SDKs, plugins, examples, contribution guides | Python SDK exists (unpublished); no plugin mechanism yet |
| Reliability | CI/CD, monitoring, alerting, availability objectives | CI live (lint, tests, coverage floor, Docker smoke test); no CD, monitoring, or SLOs |

First telemetry has landed: `GET /v1/metrics` reports request volume,
latency (avg/p50/p95), route shares (local/cloud/human), success rate,
and estimated cost per request. Still to collect, so decisions rest on
data instead of assumption: per-route latency breakdown,
routing precision (chosen route vs. best-known outcome),
memory footprint, and user satisfaction signals.

## Order of operations

The dependencies above collapse into one sequence, which is the
`Kernel → … → Adoption` trajectory made concrete. Items 1–5 are also
step 1 of [`STRATEGY.md`](STRATEGY.md) — the "real MVP" that must exist
before any commercial question is worth asking:

1. ~~Infrastructure tier 1: CI, auth, persistence~~ — ✅ done (supersedes PR #5).
2. Real LLM behind `cloud_ai` (**Capabilities**) — unblocks Produit and
   everything after.
3. ~~Docker~~ + ~~telemetry~~ (✅ both) + a public deployed instance (**Infrastructure** tier 2 — needs an owner-chosen host).
4. ~~Async human queue (**Capabilities**; makes `await_human`
   honest)~~ — ✅ done in-process; a real operator channel remains.
5. Verified Android build; voice on the web demo (**Product**).
6. ~~Versioned API~~ (✅ `/v1`) + published SDK (**Platform**).
7. Plugin discovery for classifiers/tools/actions (**Ecosystem**).
8. Third-party integrations and the public push (**Adoption**) — only
   after the demo answers real questions.

Vision (`VISION.md`) and Code hardening (mypy, coverage gate) are
parallel tracks with no dependencies; they can start any time.
