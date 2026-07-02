# AXIOMN — Vision

> AXIOMN is an open-source **intent mediation runtime**: it transforms a
> human intent into executable actions, independently of the AI model,
> the operating system, or the service provider behind it.

## The problem

Every assistant today is a silo that tries to answer everything itself.
When the request is trivial, it wastes a cloud round-trip on it. When the
request is hard, it hallucinates rather than admit a human would do
better. When the request is ambiguous, it guesses instead of asking. The
user has no idea which of these three failure modes they just got,
because the system never explains *how* it decided to answer.

## The thesis

Mediation beats monolith. A thin layer that classifies the intent and
then chooses the best resolver — a local model, a cloud model, a human —
wins on cost (easy things stay local and free), on quality (hard things
go to whoever is actually best), on honesty (impossible things reach a
human instead of being hallucinated), and on privacy (nothing leaves the
device unless the routing decision says it must). The layer is not the
answer; it is the decision about the answer.

## The invariants

These are the rules that do not change, whatever gets built on top. Every
design decision is checked against them; a feature that violates one is
wrong even if it works.

1. **Intent is the single entry point.** Everything enters as a human
   intent — text today, voice/screen/gesture tomorrow — and is
   classified before anything else happens. There is no side door where
   a request skips classification and routing.
   *In the code today:* `POST /intent` is the only functional endpoint;
   every client (SDK, web demo, Android) goes through it.

2. **Capabilities are interchangeable.** No layer may depend on a
   specific model, provider, or backend. Anything that resolves an
   intent implements a narrow contract (`ToolHandler`, `RouteProfile`,
   `IntentClassifier`) and can be swapped without touching the rest.
   *In the code today:* the heuristic and semantic classifiers are
   interchangeable behind `IntentClassifier`; tools are registered, not
   hardcoded. *Falls short:* the real cloud LLM and human queue are
   still stubs — the contract exists, the capability doesn't.

3. **Data belongs to the user.** Requests are not retained beyond what
   execution requires; nothing is sent off-device unless the routing
   decision requires it; anything learned from outcomes (trust scores)
   is operational metadata, not user content.
   *In the code today:* the local route resolves entirely in-process and
   no request content is persisted. *Falls short:* there is no per-user
   data model yet at all — this invariant must be enforced by design
   when accounts and persistence arrive, not retrofitted.

4. **The system is observable and explainable.** Every answer carries
   its own explanation: what the intent was classified as, which route
   was chosen and why, which tool ran, how long it took, how confident
   the system was. A user (or an integrating developer) can always see
   *how* the answer was produced.
   *In the code today:* the API response and the `/ui/` demo expose
   intent, route, tool, confidence, ambiguity, and execution time on
   every single request. *Falls short:* no aggregated metrics or
   structured logging yet (see ROADMAP, Infrastructure).

## Why now

On-device models finally make the local route real: a phone can resolve
a meaningful share of intents instantly, privately, and for free — which
makes *deciding what not to send to the cloud* valuable for the first
time. Simultaneously, cloud models became good enough that "route the
hard ones to the best resolver" is a real quality gain, not a fallback.
Mediation only matters when the routes genuinely differ; they now do.

## The wedge and the sequencing

SDK-first, consumer-assistant second. The first users are developers who
need routing inside their own products — they get a runtime that turns
"a user typed something" into "here is the resolved action and here is
why," without marrying a provider. Only once the runtime is proven
inside other products does a first-party assistant experience make sense
(see ROADMAP: `Kernel → … → Adoption`).

The first product is chosen (see `STRATEGY.md`): **AXIOMN Gateway** —
one API that automatically picks the best model for every request by
cost, quality, and latency, shows why, and measures the savings against
the everything-to-the-premium-model baseline. It sells a felt,
measurable pain (the LLM bill; provider lock-in) on a Thursday-evening
sales cycle, while this document's larger vision stays what it is: the
long term, discovered after adoption, never the pitch.

## The moat

The routing feedback loop. `record_outcome()` feeds real results back
into route trust scores, so routing quality compounds with usage — and
that accumulated knowledge of *who resolves what best, for these users*
belongs to the layer, not to any model behind it. Models are
substitutable (invariant 2); the learned routing is not.

## Non-goals

- Being a model. AXIOMN never competes with the systems it routes to.
- Being a walled garden. Provider lock-in anywhere in the stack violates
  invariant 2.
- Answering everything. "A human should take this" is a first-class
  outcome (`await_human`), not a failure.
