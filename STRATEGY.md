# AXIOMN — Strategy

The commercial counterpart to [`ROADMAP.md`](ROADMAP.md): the roadmap
says what to build and in what order; this document says why the project
is not for sale yet, what has to be true before that question is worth
asking, and which paths stay open.

## The premise: a technical asset is not a commercial asset

What exists today is a technical asset — a clean kernel, a tested
pipeline, honest documentation. Buyers, investors, and partners pay for
a *commercial* asset: a project that already solves a real problem for
real users, with the numbers to prove it. Selling now would price the
code, not the idea's potential. **Decision: AXIOMN is not for sale at
this stage.** The work below is what converts one kind of asset into
the other.

## The four steps, in order

### 1. Finish a real MVP

"Real" means a stranger can get value from AXIOMN in minutes, without
reading the source:

- A real LLM behind `cloud_ai` (local or cloud) — answers, not
  template strings.
- A public deployed instance with a URL.
- A working, verified Android app.
- Setup measured in minutes: try it, integrate it, see the routing
  transparency work on your own request.

These are ROADMAP items 2, 3, and 5 — the strategy adds no new
engineering, it explains why those items come before everything else.

### 2. Find the first use case

Do not try to replace Siri on day one. Pick one domain where mediation
has obvious, explainable value, and build a concrete product on top of
the kernel. Candidate wedges:

- **Multi-model orchestration for developers** — route requests across
  several LLMs (and humans) by cost/quality/privacy. *Closest to the
  SDK-first wedge already named in `VISION.md`, and the buyer already
  understands the problem.*
- **Enterprise assistant** — internal requests routed between local
  models (private data stays in), cloud models, and internal experts.
- **Intelligent customer support** — easy tickets resolved instantly,
  hard ones routed to the right human; `await_human` is literally this.
- **Education platform** — questions routed between instant answers and
  human tutors (the human queue again, with a real operator network).

The kernel stays general; the *product* is specific. Investors and
customers understand a product that answers a precise need far more
easily than a very general technology.

### 3. Create traction

The proof that step 2 worked, in ascending order of strength:

- active users,
- qualitative feedback (what they actually use it for),
- usage statistics (the telemetry in ROADMAP Infrastructure #3 exists
  precisely to measure this),
- first revenue, even small.

### 4. Then — and only then — choose the path

With traction, all options stay open and every one of them prices
higher:

- sell the technology to a company,
- raise funds and build a company around it,
- stay open source and sell services / an enterprise offering
  (open-core),
- build an independent business on top.

Choosing among these *before* traction means choosing with the least
information and the least leverage. The choice is deliberately deferred.

## The operating principle

**Keep AXIOMN as the kernel; build the first product on top of it —
never fuse the two.** The kernel's value is its generality and its
contracts (`ARCHITECTURE.md`); the product's value is its specificity.
If the product succeeds, the kernel's value exceeds the code by far —
it becomes the thing other products (step 2's siblings) are built on,
which is the `Platform → Ecosystem → Adoption` trajectory in
`ROADMAP.md`.

## What this changes about priorities

The project's constraint is no longer feature count — it is **proof of
user value**. Concretely: any work that doesn't either (a) finish the
MVP, (b) serve the first use case, or (c) measure traction, should lose
a priority contest against work that does. The quality bar in
`CONTRIBUTING.md` still applies to everything that ships; rigor is what
makes the eventual traction trustworthy.
