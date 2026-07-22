"""
crypto_envelope.py — On-the-wire OTP obfuscation (HMAC envelope)

Shared by the IoT clients and servers (REST and MQTT). Instead of sending the
raw 6-digit TOTP code in cleartext (protected only by TLS), the client wraps the
code in an HMAC envelope so the OTP never travels in the clear — even if TLS is
terminated at an upstream proxy. This hardens the scheme against network
sniffing and replay (MITRE ATT&CK T1040 / T1550), following the OTP-hardening
line of Oliveira et al. (AINA 2024) and Langaro et al.

Envelope (client -> server):
    nonce : 128-bit random hex (single-use, per request)
    ts    : Unix timestamp (seconds) at send time
    mac   : HMAC-SHA256(seed, otp_code || "|" || nonce || "|" || ts)

The server independently recomputes the TOTP code for the accepted time window,
derives the expected MAC for each candidate code, and compares in constant time.
A replay cache rejects reused nonces; a bounded timestamp skew rejects stale or
future envelopes. The seed (TOTP secret) is the HMAC key and never leaves the
device TPM / server Vault, so an attacker who observes the envelope cannot
recover the OTP or forge a new one without the seed.

Two transport modes are supported via OTP_MODE:
    - "hmac"  (default): send the HMAC envelope described above.
    - "plain" (legacy):  send the raw otp_code (backward compatibility only).

This module is dependency-free (stdlib only) so it can be vendored into each
containerized component without extra packages.
"""

from __future__ import annotations

import hmac
import time
import secrets as _secrets
import hashlib
from typing import Optional

# ── Tunables (kept in sync with the agents via .env) ─────────────────────────
DEFAULT_TS_SKEW = 90          # max |now - ts| accepted, in seconds
NONCE_BYTES = 16              # 128-bit single-use nonce
_SEP = "|"                    # field separator inside the MAC pre-image


def _mac(seed: str, otp_code: str, nonce: str, ts: int) -> str:
    """Compute HMAC-SHA256(seed, otp_code|nonce|ts) as a lowercase hex digest."""
    msg = f"{otp_code}{_SEP}{nonce}{_SEP}{ts}".encode("utf-8")
    return hmac.new(seed.encode("utf-8"), msg, hashlib.sha256).hexdigest()


def seal_otp(seed: str, otp_code: str, ts: Optional[int] = None) -> dict:
    """
    Build an HMAC envelope for the given TOTP code.

    Returns a dict {"nonce", "ts", "mac"} ready to be JSON-serialized and sent.
    The raw otp_code is NOT included — only its keyed MAC.
    """
    ts = int(time.time()) if ts is None else int(ts)
    nonce = _secrets.token_hex(NONCE_BYTES)
    return {"nonce": nonce, "ts": ts, "mac": _mac(seed, otp_code, nonce, ts)}


class ReplayCache:
    """
    Minimal in-memory single-use nonce cache with time-based eviction.

    Not shared across processes; for a multi-worker deployment back this with a
    shared store (e.g. Redis) keyed by nonce with a TTL of 2*ts_skew.
    """

    def __init__(self, ttl: int = 2 * DEFAULT_TS_SKEW):
        self.ttl = ttl
        self._seen: dict[str, float] = {}

    def _evict(self, now: float) -> None:
        stale = [n for n, exp in self._seen.items() if exp <= now]
        for n in stale:
            self._seen.pop(n, None)

    def check_and_store(self, nonce: str) -> bool:
        """Return True if nonce is fresh (and record it); False if replayed."""
        now = time.time()
        self._evict(now)
        if nonce in self._seen:
            return False
        self._seen[nonce] = now + self.ttl
        return True


def open_and_verify(
    seed: str,
    envelope: dict,
    totp,
    valid_window: int = 1,
    ts_skew: int = DEFAULT_TS_SKEW,
    replay_cache: Optional[ReplayCache] = None,
) -> bool:
    """
    Verify an HMAC envelope produced by seal_otp().

    Steps:
      1. Reject if required fields are missing or the timestamp skew is too large.
      2. Reject replayed nonces (if a ReplayCache is provided).
      3. For each TOTP code valid in [-valid_window, +valid_window] steps,
         recompute the expected MAC and compare in constant time.

    `totp` is a pyotp.TOTP instance already bound to the device seed/interval.
    Returns True only if the envelope authenticates a currently valid code.
    """
    try:
        nonce = str(envelope["nonce"])
        ts = int(envelope["ts"])
        mac = str(envelope["mac"])
    except (KeyError, TypeError, ValueError):
        return False

    now = int(time.time())
    if abs(now - ts) > ts_skew:
        return False

    if replay_cache is not None and not replay_cache.check_and_store(nonce):
        return False

    # Enumerate candidate codes across the accepted time window and match MACs.
    step = getattr(totp, "interval", 60)
    for drift in range(-valid_window, valid_window + 1):
        candidate = totp.at(now + drift * step)
        expected = _mac(seed, candidate, nonce, ts)
        if hmac.compare_digest(expected, mac):
            return True
    return False
