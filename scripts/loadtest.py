#!/usr/bin/env python3
"""Small async load test for a running AXIOMN instance.

Fires a fixed number of requests at a chosen endpoint with bounded concurrency
and reports throughput, latency percentiles, and the error rate — the numbers
that turn "nice architecture" into "measured under load".

Pure stdlib + httpx (already an AXIOMN dependency). No execution side effects:
`/v1/estimate` is a dry run and needs no API key, which makes it the safe
default target for load testing a public instance.

Examples
--------
    # Estimate endpoint (no key needed), 500 requests, 50 in flight:
    python scripts/loadtest.py --url https://axiomn.fly.dev \
        --endpoint estimate --requests 500 --concurrency 50

    # Full intent pipeline (add --api-key if the instance requires one):
    python scripts/loadtest.py --url http://localhost:8000 \
        --endpoint intent --requests 200 --concurrency 20
"""
from __future__ import annotations

import argparse
import asyncio
import statistics
import time

import httpx

_PROMPTS = [
    "Explain how black holes form",
    "hi",
    "what is 2 + 2",
    "Write a full go-to-market strategy for a B2B SaaS",
    "Find me a tax law expert",
    "Summarize this text in one sentence",
]


def _payload(endpoint: str) -> tuple[str, dict]:
    if endpoint == "estimate":
        return "/v1/estimate", {"texts": _PROMPTS}
    return "/v1/intent", {"text": _PROMPTS[0]}


async def _worker(
    client: httpx.AsyncClient, path: str, body: dict, headers: dict,
    sem: asyncio.Semaphore, latencies: list[float], errors: list[int],
) -> None:
    async with sem:
        start = time.perf_counter()
        try:
            resp = await client.post(path, json=body, headers=headers)
            latencies.append((time.perf_counter() - start) * 1000)
            if resp.status_code >= 400:
                errors.append(resp.status_code)
        except httpx.HTTPError:
            latencies.append((time.perf_counter() - start) * 1000)
            errors.append(-1)


def _pct(values: list[float], p: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    k = min(len(ordered) - 1, int(round(p / 100 * (len(ordered) - 1))))
    return ordered[k]


async def _run(args: argparse.Namespace) -> None:
    path, body = _payload(args.endpoint)
    headers = {"X-API-Key": args.api_key} if args.api_key else {}
    latencies: list[float] = []
    errors: list[int] = []
    sem = asyncio.Semaphore(args.concurrency)

    async with httpx.AsyncClient(base_url=args.url.rstrip("/"), timeout=args.timeout) as client:
        wall_start = time.perf_counter()
        await asyncio.gather(
            *(_worker(client, path, body, headers, sem, latencies, errors)
              for _ in range(args.requests))
        )
        wall = time.perf_counter() - wall_start

    ok = len(latencies) - len(errors)
    print(f"\nAXIOMN load test — {args.endpoint} @ {args.url}")
    print(f"  requests      : {args.requests} (concurrency {args.concurrency})")
    print(f"  wall time     : {wall:.2f}s")
    print(f"  throughput    : {args.requests / wall:.1f} req/s")
    print(f"  success       : {ok}/{args.requests} ({100 * ok / args.requests:.1f}%)")
    if errors:
        codes = ", ".join(f"{c}×{errors.count(c)}" for c in sorted(set(errors)))
        print(f"  errors        : {len(errors)} ({codes})")
    if latencies:
        print(f"  latency p50   : {_pct(latencies, 50):.0f} ms")
        print(f"  latency p95   : {_pct(latencies, 95):.0f} ms")
        print(f"  latency p99   : {_pct(latencies, 99):.0f} ms")
        print(f"  latency mean  : {statistics.mean(latencies):.0f} ms")


def main() -> None:
    parser = argparse.ArgumentParser(description="Load test a running AXIOMN instance.")
    parser.add_argument("--url", default="http://localhost:8000", help="Base URL of the instance.")
    parser.add_argument("--endpoint", choices=["estimate", "intent"], default="estimate")
    parser.add_argument("--requests", type=int, default=200, help="Total requests to send.")
    parser.add_argument("--concurrency", type=int, default=20, help="Max requests in flight.")
    parser.add_argument("--timeout", type=float, default=30.0, help="Per-request timeout (s).")
    parser.add_argument("--api-key", default=None, help="X-API-Key, if the instance requires one.")
    asyncio.run(_run(parser.parse_args()))


if __name__ == "__main__":
    main()
