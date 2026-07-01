# AXIOMN

**The universal intent mediation layer.**

AXIOMN turns a human intent — expressed in any language, as text today,
as voice/screen/gesture tomorrow — into a routed, resolved action. It is
not an assistant, an app, or a single model: it's the layer that decides
*how* a request should be answered, then hands it to whichever system
(a local model, a cloud model, a human expert) is the best fit, instead
of being the answer itself.

This repository is a real, testable slice of that idea: a full
`Intent Engine -> Router -> Execution Layer -> Action Engine` pipeline, a
Python SDK, and a small web demo, all backed by a test suite that actually
exercises the claims below. It doesn't claim to replace Siri or Google
Assistant; it's the seed a real "intent OS" would be built on.

## Architecture

```
text/voice input
      |
      v
 Intent Engine    -> classifies category, topic, language, difficulty,
      |               confidence, and ambiguity (pluggable classifier:
      |               keyword heuristic or semantic embeddings)
      v
    Router         -> scores every route by capability fit, cost, latency,
      |               trust, category affinity, and ambiguity — not a
      |               fixed threshold. A confident-but-ambiguous request
      |               (two categories effectively tied) can outrank a
      |               cheaper route even at moderate difficulty, because
      |               a human can just ask a clarifying question.
      v
 Execution Layer   -> asks the Tool Registry for the best tool for that route,
      |               runs it, times it, and reports success/failure back
      |               to the Router so future routing reflects real outcomes
      +-- local_ai     instant, on-device / heuristic resolution
      +-- cloud_ai      a real LLM call for harder requests (stub, pluggable)
      +-- human_queue   escalation to a human/expert network (stub, pluggable)
      |
      v
  Action Engine     -> a raw text result isn't enough for a client to act on;
      |               this decides what to *do* with it: speak it, copy it,
      |               open a link, schedule it — or, if the route was
      |               human_queue, surface "still working on it" instead of
      |               going silent, since that answer isn't ready yet
      v
   result + action (+ which tool ran, and how long it took)
```

Each layer is a small, independently testable component with a narrow
contract:

| Module | Responsibility |
|---|---|
| `axiomn/intent/engine.py` | `classify(text) -> Intent` (category, topic, language, difficulty, confidence, ambiguity) |
| `axiomn/intent/classifiers.py` | `HeuristicIntentClassifier`: keyword-overlap, offline, default. Returns a `Classification` (category, confidence, *and* ambiguity — the gap between the winning category and the runner-up) |
| `axiomn/intent/embedding.py` | `SemanticIntentClassifier`: nearest-neighbor in embedding space — matches by meaning, works across languages without translation (optional, see below); ambiguity comes from the gap between the best and second-best category's similarity |
| `axiomn/router/router.py` | `Router.route(intent) -> Route`, a cost/latency/trust/ambiguity-scoring policy over `RouteProfile`s; `record_outcome()` updates trust from real results |
| `axiomn/models/tools.py` | `ToolRegistry`: named, tagged tools per route, so a route isn't tied to exactly one backend |
| `axiomn/execution/engine.py` | `ExecutionEngine.execute(route, intent) -> ExecutionOutcome`, picks a tool, times it, closes the feedback loop to the Router |
| `axiomn/action/engine.py` | `ActionEngine.decide(intent, route, result_text) -> Action`: `voice_reply`, `copy_to_clipboard`, `open_url`, `schedule_task`, or `await_human` (always wins when `route == human_queue`, regardless of category — the async escalation isn't done yet) |
| `axiomn/api/main.py` | FastAPI app wiring the pipeline behind `POST /intent`, plus a static demo at `/ui/` |
| `sdk/axiomn_sdk/` | Standalone Python client package (`pip install -e sdk/`) — depends only on `httpx`, not on the server |

Every extension point (`IntentClassifier`, `ToolHandler`, `RouteProfile`)
is a narrow, swappable contract — the same design principle applied at
every layer, so a real LLM client or a human-queue integration replaces a
stub without touching the router or the API.

## Running it

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
pip install -e .          # the axiomn package itself
pip install -e sdk/       # the SDK client, used by sdk/tests

# run the full test suite (server + SDK)
pytest -q

# run the API + web demo
uvicorn axiomn.api.main:app --reload
```

Open `http://127.0.0.1:8000/ui/` for a minimal page that shows not just
the answer but *how AXIOMN decided to produce it* (intent, route, tool,
confidence, execution time) — or call the API directly:

```bash
curl -X POST http://127.0.0.1:8000/intent \
  -H "Content-Type: application/json" \
  -d '{"text": "Explique-moi comment fonctionnent les trous noirs"}'
```

```json
{
  "intent": "learn",
  "topic": "Explique-moi comment fonctionnent trous noirs",
  "language": "fr",
  "difficulty": 1,
  "confidence": 0.8,
  "ambiguity": 0.0,
  "route": "local_ai",
  "tool": "local_heuristic",
  "result": "[local] learn answer for: Explique-moi comment fonctionnent trous noirs",
  "execution_time_ms": 0.01,
  "action": { "type": "voice_reply", "payload": { "text": "[local] learn answer for: ..." } }
}
```

A request that escalates to a human (e.g. `route == "human_queue"`) gets
`"action": {"type": "await_human", ...}` instead — the client's cue that
there's no answer yet, rather than silently treating the queued message
as the final reply.

### SDK usage

```python
from axiomn_sdk import AXIOMNClient

with AXIOMNClient(base_url="http://localhost:8000") as client:
    result = client.intent("Explain how black holes form")
    print(result.route, result.result)
```

### Optional: semantic (embeddings) classification

The default `HeuristicIntentClassifier` is keyword-based, offline, and
fast — the whole test suite runs in under a second because of it. For
real cross-lingual, meaning-based classification, swap in
`SemanticIntentClassifier`:

```bash
pip install -r requirements-semantic.txt
```

```python
from axiomn.intent.embedding import SemanticIntentClassifier, SentenceTransformerEmbedder
from axiomn.intent.engine import IntentEngine

engine = IntentEngine(classifier=SemanticIntentClassifier(SentenceTransformerEmbedder()))
```

This is opt-in rather than the default because it downloads a ~470MB
multilingual model on first use. It's verified in
`tests/test_semantic_intent_live.py` (skipped by default; run with
`AXIOMN_LIVE_TESTS=1`), which confirms that "explain how black holes
form", its French translation, and its Japanese translation all land in
the same category — by meaning, with no translation step.

### Operations: auth, rate limiting, persistence

All three are opt-in and off by default, so local dev and the existing
test suite need zero setup. Nothing below is enabled unless you set the
corresponding environment variable.

| Env var | Default | Effect |
|---|---|---|
| `AXIOMN_API_KEYS` | unset (auth disabled) | Comma-separated list of accepted keys. When set, `POST /intent` requires a matching `X-API-Key` header (401 otherwise). **Unset means the endpoint is wide open** — set this before exposing AXIOMN beyond your own machine. |
| `AXIOMN_RATE_LIMIT_PER_MINUTE` | `60` | Max requests per client (per API key, or per IP if no key) per rolling 60s window. In-memory only — resets on restart, and doesn't share state across multiple server processes. |
| `AXIOMN_ROUTER_STATE_PATH` | unset (no persistence) | Path to a JSON file where the Router's trust scores are saved after every `record_outcome()` and reloaded on startup. Unset means every restart forgets what the Router has learned. |

```bash
AXIOMN_API_KEYS=my-secret-key AXIOMN_ROUTER_STATE_PATH=./router_state.json uvicorn axiomn.api.main:app
```

CI (`.github/workflows/ci.yml`) runs `ruff check` and the full test suite
on every push and pull request.

### Mobile client

`android/` has a push-to-talk Android MVP (mic button → speech-to-text →
this API → spoken reply) that talks to the exact schema above. See
`android/README.md` — it's unverified in this environment (no Android SDK
available here to build it) and deliberately doesn't attempt a wake-word
or background-service "always listening" mode; details on both in that
file.

## What's deliberately out of scope here

This is a backend pipeline, an SDK, a demo UI, and a mobile client — not
the "OS layer" described in the long-form vision behind AXIOMN (iOS
assistant replacement, multi-device orchestration, a live human expert
network, a real cloud LLM backend). Those are real, larger efforts that
build on top of the same `Intent -> Route -> Execute` contract
established here; they're not attempted in this repository because they
can't be built *and verified* in this environment.
