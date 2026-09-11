"""The collector interface every source implements."""

from __future__ import annotations

import logging
from pathlib import Path

from .config import StoreConfig
from .errors import FetchError
from .models import SalesRow
from .retry import retry_call

log = logging.getLogger(__name__)


class Collector:
    """Two steps, always in this order: fetch() then parse().

    Splitting them is the whole point of the design:

      * fetch() is the part that touches the outside world and is therefore the
        part that is retried.
      * parse() is pure -- raw payload in, normalised rows out -- so every
        source can be tested against a saved fixture with no network at all,
        which is exactly what this demo does.

    A real HTTP collector subclasses this and replaces fetch() with a request.
    Nothing else in the pipeline changes.
    """

    #: Name used in stores.yaml (`collector:`). Set by each subclass.
    type_name: str = ""

    def __init__(self, store: StoreConfig) -> None:
        self.store = store
        #: Fetch attempts actually used, readable after collect() succeeds or
        #: fails. The run report distinguishes "the source was flaky" from
        #: "the source answered but had changed", and that needs this number
        #: even when the failure happened later, during parse().
        self.attempts_used = 0

    def fetch(self) -> str:
        """Return the raw payload. Here: read the local fixture file.

        In production this is the HTTP request, the SFTP download or the IMAP
        session. The demo keeps the same shape so the swap is a one-class job.
        """
        path: Path = self.store.source
        self._simulate_transient_failure()
        try:
            return path.read_text(encoding=self.store.options.get("encoding", "utf-8"))
        except OSError as error:
            raise FetchError(f"could not read source {path.name}: {error}") from error

    def parse(self, raw: str) -> list[SalesRow]:
        raise NotImplementedError

    def collect(self) -> tuple[list[SalesRow], int]:
        """fetch (with retry) then parse. Returns rows and attempts used."""
        label = f"{self.store.id} {self.store.name}"
        raw, attempts = retry_call(self.fetch, self.store.retry, label)
        self.attempts_used = attempts
        rows = self.parse(raw)
        log.info("%s: parsed %d row(s) via %s", label, len(rows), self.type_name)
        return rows, attempts

    # -- demo scaffolding -------------------------------------------------
    def _simulate_transient_failure(self) -> None:
        """Fail the first N fetches for stores configured with `simulate`.

        Demo-only, and confined to this one method so it is obvious what is
        real and what is staged. It exists because a retry policy nobody can
        see working is a retry policy nobody trusts.
        """
        failures = int(self.store.simulate.get("fetch_failures", 0))
        if not failures:
            return
        seen = self.store.simulate.setdefault("_seen", 0)
        if seen < failures:
            self.store.simulate["_seen"] = seen + 1
            raise FetchError(
                f"simulated transient network error (attempt {seen + 1} of {failures} staged)"
            )
