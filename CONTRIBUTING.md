# Contributing to AXIOMN

The bar this project holds itself to: **rigor before size**. Projects
like Linux, Git, and Kubernetes became huge because they were reliable,
coherent, and well designed first. Contributions are judged by that
standard, whatever their size.

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
pip install -e sdk/

pytest -q                      # full suite (server + SDK) — must pass
ruff check axiomn sdk tests    # lint — must be clean
```

## The working method

1. **Principles first, features second.** Before writing code, check the
   change against the invariants in [`VISION.md`](VISION.md) and the
   rules in [`ARCHITECTURE.md`](ARCHITECTURE.md). A feature that
   violates an invariant is wrong even if it works.

2. **Respect the layer contracts.** New capability → `ToolHandler`. New
   resolver → `RouteProfile`. New input understanding →
   `IntentClassifier`. If your change can't fit an existing contract and
   forces edits across layers, open a discussion first — that's an
   architecture review, not a pull request.

3. **Everything is tested.** No behavior lands without a test that
   exercises it. Tests exercise real behavior, not mocks of the thing
   under test (the SDK suite runs against a live loopback server; the
   web demo was verified in a real browser).

4. **Every bug fix ships with its regression test.** The test must fail
   before the fix and pass after. A bug that was possible once is
   possible again unless a test forbids it.

5. **Measure instead of assuming.** Claims about latency, routing
   quality, cost, or memory belong in a test or a benchmark, not in a
   commit message. If you assert your change makes something better,
   include the number.

6. **Document as if another team takes over tomorrow.** A change that
   alters behavior updates the docs in the same PR: `README.md` for
   usage, `ARCHITECTURE.md` for contracts, `ROADMAP.md` if it moves a
   roadmap item. Public contracts carry docstrings — they are the
   extension API and should read like one.

7. **All code is reviewed.** Nothing merges to `main` without a pull
   request and a review. Review feedback is a feature of the process,
   not friction: the ambiguity-routing change (PR #4) is the precedent —
   a proposed rewrite was caught in review as a silent regression and
   landed as a safe, additive change instead.

8. **Honest PRs.** State what was verified and how, and what was *not*
   verified (see PR #3's Android caveat for the standard). A green
   checklist that hides an untested path is worse than a red one.

## Quality bar

These are the targets contributions move toward, never away from
(current enforcement status in [`ROADMAP.md`](ROADMAP.md)):

| Area | Target |
|---|---|
| Tests | Coverage > 90%, enforced in CI; guarantees are tests (see ARCHITECTURE rule 3) |
| Typing | Strict type checking (`mypy --strict`), enforced in CI |
| Style | `ruff check` clean |
| API | Versioned schema; breaking changes are platform events, not patches |
| Security | No secrets in the repo, ever; auth on by default in deployments; dependencies audited |
| Performance | Local route stays instant; the full default test suite stays fast (seconds, not minutes) |

## Pull request checklist

- [ ] `pytest -q` passes; new behavior has new tests
- [ ] `ruff check axiomn sdk tests` is clean
- [ ] Bug fix? The regression test is in the diff
- [ ] Contract change? `ARCHITECTURE.md` updated; SDK/clients updated together
- [ ] Behavior change? Docs updated in the same PR
- [ ] The PR description says what was verified, how, and what wasn't
