"""Rebuild a candidate's trend report as soon as one of their cases is marked.

Nothing else builds a trend report. Before this hook the Development page showed
whatever was built the last time something happened to call generate-trend,
which in practice meant a candidate finished a case, read their feedback, opened
Development, and were shown patterns drawn from every case *except* the one they
had just sat. Marking now pokes the app's own endpoint on the way out.

Fire and forget, deliberately:

- The trend build takes one to two minutes. This request waits a couple of
  seconds for the far side to take the work and then walks away, so the marking
  response is never held behind it. Azure Functions keeps executing an
  invocation it has already accepted after the caller disconnects, so the report
  is still built; the timeout is expected, not an error, and is logged as such.
- Every failure is swallowed. A candidate's marking result is the thing they
  paid for. It must never be delayed, and it must never fail, because the trend
  layer was busy, rate limited, or misconfigured.

Concurrency: two cases marked at once means two builds for one candidate. There
is no claim or lock. What there is, is the unique index on
trend_reports.candidate_id (migration 0003) and the upsert in
SessionRepository.save_trend, so the two builds converge on one row and the
later write wins rather than the table growing a duplicate. Both builds do pay
for their model call.
"""
from __future__ import annotations

import logging
import os
from typing import Any, Awaitable, Callable, Dict, Optional

import httpx

logger = logging.getLogger(__name__)

TREND_TRIGGER_PATH = "/api/generate-trend"

# Long enough for the far side to accept the request, short enough that a
# marking response is never visibly slower for it. The far side finishing the
# work is not what we are waiting for.
TREND_TRIGGER_TIMEOUT_SECONDS = 2.5

# (url, json_body, headers) -> None
Poster = Callable[[str, Dict[str, Any], Dict[str, str]], Awaitable[None]]


def resolve_self_base_url(settings: Any) -> Optional[str]:
    """Where this Function app can reach itself, or None if it cannot tell.

    SELF_BASE_URL wins wherever it is set: local dev (http://localhost:7071), a
    deployment slot, or a custom domain. Otherwise WEBSITE_HOSTNAME, which Azure
    Functions sets on every instance to the app's own hostname
    (caseforge2025a.azurewebsites.net) and which is always reachable over https.

    Returning None is a normal outcome, not a failure: it is what happens when
    marking runs outside Azure with nothing configured, and the trigger then
    does nothing rather than guessing at a URL.
    """
    explicit = str(getattr(settings, "self_base_url", "") or "").strip()
    if explicit:
        return explicit.rstrip("/")

    hostname = (os.environ.get("WEBSITE_HOSTNAME") or "").strip()
    return f"https://{hostname}" if hostname else None


async def _post(url: str, json_body: Dict[str, Any], headers: Dict[str, str]) -> None:
    async with httpx.AsyncClient(timeout=TREND_TRIGGER_TIMEOUT_SECONDS) as client:
        await client.post(url, json=json_body, headers=headers)


async def fire_trend_rebuild(
    candidate_id: Optional[str],
    settings: Any,
    *,
    post: Optional[Poster] = None,
) -> bool:
    """Ask this app to rebuild one candidate's trend report. Never raises.

    Returns True when the request was sent and answered inside the timeout,
    False in every other case, including the ordinary one where the build is
    still running when we stop waiting. The caller is expected to ignore it: the
    return value is for tests and for reading the logs, not for control flow on
    the marking path.
    """
    if not candidate_id:
        logger.info("No candidate id on the marked result; trend rebuild not triggered.")
        return False

    base_url = resolve_self_base_url(settings)
    if not base_url:
        logger.info(
            "Neither SELF_BASE_URL nor WEBSITE_HOSTNAME is set; trend rebuild for "
            "candidate %s not triggered.",
            candidate_id,
        )
        return False

    url = f"{base_url}{TREND_TRIGGER_PATH}"
    headers = {"Content-Type": "application/json"}
    # The same secret that guards mark-consultation guards generate-trend. When
    # it is unset the endpoint does not check, and neither do we.
    secret = str(getattr(settings, "marking_shared_secret", "") or "")
    if secret:
        headers["x-marking-secret"] = secret

    sender = post or _post
    try:
        await sender(url, {"candidateId": candidate_id}, headers)
    except Exception as exc:  # noqa: BLE001 - the marking response owns this path
        logger.warning(
            "Trend rebuild for candidate %s did not complete within %.1fs (%s: %s). "
            "The build may still be running; the marking result is unaffected.",
            candidate_id,
            TREND_TRIGGER_TIMEOUT_SECONDS,
            type(exc).__name__,
            exc,
        )
        return False

    logger.info("Trend rebuild triggered for candidate %s.", candidate_id)
    return True
