"""Sandboxed execution for AXIOMN's Executor Core.

The Router can decide an intent needs to *run code*, not just *answer* it.
Running that code in-process would be unsafe and unprovable. This package wires
the Executor Core to VERITY (`V-rify-IA`), the sibling system that executes
untrusted code in an isolated sandbox and returns an Ed25519-signed proof of
exactly what ran and what it produced — the "Sandbox sécurisé" box of the
unified architecture (see `UNIFIED_ARCHITECTURE.md`).

The integration is **opt-in and fail-open**: with no `AXIOMN_VERITY_URL`
configured, AXIOMN behaves exactly as before, and if a configured sandbox is
unreachable the handler degrades to a plain local result instead of erroring.
"""
from .verity import VeritySandboxHandler, build_verity_handler

__all__ = ["VeritySandboxHandler", "build_verity_handler"]
