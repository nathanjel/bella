#!/usr/bin/env python3
"""service-easy: a request handler that signs and verifies session tokens (itsdangerous, BSD-3).

    tokens.py REQUESTS.jsonl

A handler function `handle(request) -> response` driven by a fixed list of JSON requests
(sign a payload, verify a token, verify an expired or tampered token). No sockets: the service
boundary is the function, which is what a WSGI/ASGI app is before the server wraps it.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from itsdangerous import BadSignature, SignatureExpired, TimestampSigner, URLSafeTimedSerializer

SECRET = "bella-phase-0"  # noqa: S105 -- test fixture


class Clock:
    """Deterministic time source so expiry checks are reproducible; advanced by requests."""

    def __init__(self, now: int) -> None:
        self.now = now


class ClockedSigner(TimestampSigner):
    """itsdangerous reads the time in the *signer*, so the clock is injected there."""

    clock: Clock  # attached by ClockedSerializer.make_signer

    def get_timestamp(self) -> int:
        return self.clock.now


class ClockedSerializer(URLSafeTimedSerializer):
    """Every signer this serializer makes shares the injected clock instead of time.time()."""

    def __init__(self, clock: Clock, secret_key: str, salt: str) -> None:
        super().__init__(secret_key, salt=salt, signer=ClockedSigner)
        self.clock = clock

    def make_signer(self, salt: str | bytes | None = None) -> ClockedSigner:
        signer = super().make_signer(salt)
        assert isinstance(signer, ClockedSigner)
        signer.clock = self.clock
        return signer


def handle(request: dict[str, object], serializer: ClockedSerializer) -> dict[str, object]:
    op = request["op"]
    serializer.clock.now += int(request.get("advance", 0))  # type: ignore[call-overload]
    if op == "sign":
        token = serializer.dumps(request["payload"])
        return {"status": 200, "token": token, "signed_at": serializer.clock.now}
    if op == "verify":
        try:
            payload = serializer.loads(str(request["token"]), max_age=int(request.get("max_age", 3600)))  # type: ignore[call-overload]
        except SignatureExpired as exc:
            signed = int(exc.date_signed.timestamp()) if exc.date_signed else None
            return {"status": 401, "error": "expired", "signed_at": signed, "now": serializer.clock.now}
        except BadSignature:
            return {"status": 400, "error": "bad signature"}
        return {"status": 200, "payload": payload}
    return {"status": 404, "error": f"unknown op {op!r}"}


def main(path: str) -> int:
    serializer = ClockedSerializer(Clock(1_700_000_000), SECRET, salt="session")
    tokens: dict[str, str] = {}
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        request = json.loads(line)
        if "token_ref" in request:
            request["token"] = tokens[request["token_ref"]] + request.get("tamper", "")
            if request.get("flip"):   # the same length, one signature character changed
                token = str(request["token"])
                request["token"] = token[:-1] + ("A" if token[-1] != "A" else "B")
        response = handle(request, serializer)
        if "token" in response:   # the whole token is the observable (review 2026-11-01, A4-5)
            tokens[str(request["name"])] = str(response["token"])
        print(json.dumps({"request": request.get("name"), "response": response}, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))
