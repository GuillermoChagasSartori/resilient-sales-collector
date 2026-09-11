"""Error types.

Fetching and parsing fail for genuinely different reasons -- the source was
unreachable vs. the source answered but no longer looks the way we expect.
The run report shows the distinction, because it tells the operator whether to
check the network or to check whether a store changed its report layout.
"""


class CollectorError(Exception):
    """Base class for every failure a single store can raise."""


class FetchError(CollectorError):
    """The raw payload could not be obtained (missing file, timeout, auth)."""


class ParseError(CollectorError):
    """The payload was obtained but does not match the expected structure."""


class ConfigError(CollectorError):
    """The store's configuration entry is unusable (bad type, missing field)."""
