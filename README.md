# AXIOMN

**The universal intent mediation layer.**

AXIOMN turns a human intent — expressed in any language, as text today,
as voice/screen/gesture tomorrow — into a routed, resolved action. It is
not an assistant, an app, or a single model: it's the layer that decides
*how* a request should be answered, then hands it to whichever system
(a local model, a cloud model, a human expert) is the best fit, instead
of being the answer itself.

This repository is the first concrete slice of that idea: a small,
real, testable pipeline — `Intent Engine -> Router -> Execution Layer`
exposed over an HTTP API. It doesn't claim to replace Siri or Google
Assistant; it's the seed a real "intent OS" would be built on.

## Architecture

```
text/voice input
      |
      v
 Intent Engine   -> classifies category, topic, language, difficulty
      |
      v
    Router        -> picks a route based on difficulty/category
      |
      v
 Execution Layer  -> dispatches to the matching backend
      |
      +-- local_ai     instant, on-device / heuristic resolution
      +-- cloud_ai      a real LLM call for harder requests (stub, pluggable)
      +-- human_queue   escalation to a human/expert network (stub, pluggable)
      |
      v
   result
```

Each layer is a small, independently testable component with a narrow
contract:

| Module | Responsibility |
|---|---|
| `axiomn/intent/engine.py` | `classify(text) -> Intent` (category, topic, language, difficulty, confidence) |
| `axiomn/router/router.py` | `route(intent) -> Route` |
| `axiomn/execution/engine.py` | `execute(route, intent) -> str`, dispatches to a `Backend` |
| `axiomn/models/backends.py` | Pluggable backends (`local_ai`, `cloud_ai`, `human_queue`) |
| `axiomn/api/main.py` | FastAPI app wiring the pipeline behind `POST /intent` |

The `Backend` contract (`run(intent) -> str`) is intentionally minimal so a
real LLM client or a human-queue integration can be dropped in later
without touching the router or the API.

## Running it

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt

# run the test suite
pytest -q

# run the API
uvicorn axiomn.api.main:app --reload
```

Then:

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
  "difficulty": 2,
  "confidence": 0.8,
  "route": "local_ai",
  "result": "[local] learn answer for: Explique-moi comment fonctionnent trous noirs"
}
```

## What's deliberately out of scope here

This MVP is a backend pipeline, not the "OS layer" described in the
long-form vision behind AXIOMN (Android/iOS assistant replacement,
multi-device orchestration, human expert network, SDK ecosystem). Those
are real, larger efforts — a mobile client, a real LLM/cloud backend, and
a human-queue integration — that build on top of the same
`Intent -> Route -> Execute` contract established here.
