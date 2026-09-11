"""Retry with exponential backoff for the fetch step only.

Parsing is deliberately *not* retried: if a page's layout changed, retrying
produces the same failure three times and hides the real cause. Retries are for
the transient class of problem -- a timeout, a 502, a locked export file.
"""

from __future__ import annotations

import logging
import time
from typing import Callable, TypeVar

from .config import RetryPolicy

T = TypeVar("T")
log = logging.getLogger(__name__)


def retry_call(
    func: Callable[[], T],
    policy: RetryPolicy,
    label: str,
    sleep: Callable[[float], None] = time.sleep,
) -> tuple[T, int]:
    """Call `func` until it succeeds or attempts run out.

    Returns the result and the number of attempts used, because the attempt
    count belongs in the run report -- a store that needed three tries today is
    a store worth watching, even though it succeeded.
    """
    delay = policy.backoff_seconds
    last_error: Exception | None = None

    for attempt in range(1, policy.attempts + 1):
        try:
            result = func()
            if attempt > 1:
                log.info("%s: fetch succeeded on attempt %d/%d", label, attempt, policy.attempts)
            return result, attempt
        except Exception as error:  # noqa: BLE001 - deliberately broad, see below
            # Broad by design: a collector may raise anything its underlying
            # library raises. The runner classifies it afterwards; swallowing
            # it here is what keeps one store's failure off the other ten.
            last_error = error
            if attempt == policy.attempts:
                break
            log.warning(
                "%s: fetch attempt %d/%d failed (%s: %s) - retrying in %.1fs",
                label, attempt, policy.attempts, type(error).__name__, error, delay,
            )
            sleep(delay)
            delay *= policy.backoff_multiplier

    assert last_error is not None
    log.error(
        "%s: fetch failed after %d attempt(s) (%s)",
        label, policy.attempts, type(last_error).__name__,
    )
    raise last_error
