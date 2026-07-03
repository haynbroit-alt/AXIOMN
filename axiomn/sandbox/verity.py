"""VERITY sandbox handler: the Executor Core's "Sandbox sécurisé".

When the Router sends a code-execution intent here, the code runs not in
AXIOMN's own process but inside VERITY (`V-rify-IA`), which sandboxes it and
returns an Ed25519-signed proof of what actually executed. AXIOMN keeps the
proof id and signature in `ToolResult.metadata` so downstream stages (and the
audit trail) can verify the run independently — no trust in AXIOMN required.

Design constraints, mirroring the Gateway/LLM-fallback wiring already in the
runtime:

* **Opt-in.** Nothing here runs unless `AXIOMN_VERITY_URL` is set (or a URL is
  passed explicitly). `build_verity_handler()` returns ``None`` otherwise, so
  `default_registry` simply doesn't register a sandbox tool and behavior is
  unchanged.
* **Fail-open.** A sandbox that is unreachable, slow, or erroring must not take
  the runtime down with it. On any transport/HTTP failure the handler returns a
  ``ToolResult(success=False)`` whose metadata explains the degradation, rather
  than raising — the Router records the failure and adapts, exactly as it does
  for any other tool that fails.
* **No new dependency.** Uses `httpx`, already a first-class AXIOMN dependency
  (the Gateway speaks to providers through it), and accepts an injectable
  `httpx.BaseTransport` so it is testable without a live VERITY instance.
"""
from __future__ import annotations

import os
from typing import Optional

import httpx

from ..intent.schema import Intent
from ..models.tools import ToolResult

DEFAULT_TIMEOUT_S = 30.0
# VERITY caps sandbox execution at 30s; keep AXIOMN's request budget within it.
DEFAULT_EXEC_TIMEOUT_S = 5


class VeritySandboxHandler:
    """A `ToolHandler` that executes an intent's payload in VERITY's sandbox.

    The intent's ``text`` is treated as the code to run — the Router only sends
    execution-shaped intents down this path. The returned ``ToolResult`` carries
    the sandbox's stdout as its output and the full proof in ``metadata`` under
    the ``verity`` key, including the signature and the ``action_id`` a caller
    can re-verify against VERITY's public key.
    """

    def __init__(
        self,
        base_url: str,
        *,
        language: str = "python",
        exec_timeout_s: int = DEFAULT_EXEC_TIMEOUT_S,
        agent_id: str = "axiomn-executor",
        timeout: float = DEFAULT_TIMEOUT_S,
        transport: Optional[httpx.BaseTransport] = None,
    ):
        self.base_url = base_url.rstrip("/")
        self.language = language
        self.exec_timeout_s = exec_timeout_s
        self.agent_id = agent_id
        self._client = httpx.Client(
            base_url=self.base_url,
            timeout=timeout,
            transport=transport,
            headers={"content-type": "application/json"},
        )

    def run(self, intent: Intent) -> ToolResult:
        try:
            response = self._client.post(
                "/v1/verify",
                json={
                    "agent_id": self.agent_id,
                    "payload": intent.text,
                    "constraints": {
                        "language": self.language,
                        "timeout": self.exec_timeout_s,
                    },
                    "verification_rules": [],
                },
            )
            response.raise_for_status()
            data = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            # Fail-open: the sandbox is unavailable, but the runtime stays up.
            # success=False lets the Router learn this route is degraded.
            return ToolResult(
                output=f"[sandbox-unavailable] could not reach VERITY: {exc}",
                success=False,
                metadata={"verity": {"available": False, "error": str(exc)}},
            )

        execution = data.get("execution") or {}
        verification = data.get("verification") or {}
        proof = data.get("proof") or {}

        verified = bool(verification.get("passed", False))
        exit_code = execution.get("exit_code", -1)
        stdout = execution.get("stdout", "")
        # A run is a success only if the sandbox executed it cleanly *and*
        # VERITY's verification rules passed — a signed proof of failure is
        # still a failure to report back to the Router.
        success = verified and exit_code == 0

        return ToolResult(
            output=stdout if stdout else "[sandbox] executed with no stdout",
            success=success,
            metadata={
                "verity": {
                    "available": True,
                    "verified": verified,
                    "status": data.get("status"),
                    "action_id": data.get("action_id"),
                    "exit_code": exit_code,
                    "execution_time_ms": execution.get("execution_time_ms"),
                    "signature": proof.get("signature"),
                    "security_flags": verification.get("security_flags", []),
                    "violations": verification.get("violations", []),
                }
            },
        )

    def close(self) -> None:
        self._client.close()


def build_verity_handler(
    base_url: Optional[str] = None,
    *,
    transport: Optional[httpx.BaseTransport] = None,
) -> Optional[VeritySandboxHandler]:
    """Construct a sandbox handler from config, or ``None`` when unconfigured.

    Resolution order for the VERITY endpoint: the explicit ``base_url``
    argument, then ``AXIOMN_VERITY_URL``. When neither is present the runtime
    has not opted into sandboxed execution, so this returns ``None`` and the
    registry omits the sandbox tool entirely — the opt-in, no-surprise default.
    """
    url = base_url or os.environ.get("AXIOMN_VERITY_URL")
    if not url:
        return None
    language = os.environ.get("AXIOMN_VERITY_LANGUAGE", "python")
    return VeritySandboxHandler(url, language=language, transport=transport)
