"""
The honesty contract.

Nothing in this system may invent data. When a capability has no real data source
(missing API key, no connector, no portfolio, site unreachable) it must say so explicitly instead of
returning plausible-looking output. Code paths raise ``NotConfiguredError``; the API turns that into
HTTP 503 ``{"status": "not_configured"}``.
"""


class NotConfiguredError(RuntimeError):
    """A capability needs credentials or data that have not been provided."""

    def __init__(self, capability: str, hint: str):
        super().__init__(hint)
        self.capability = capability
        self.hint = hint

    def to_dict(self) -> dict:
        return {"status": "not_configured", "capability": self.capability, "detail": self.hint}


class PreconditionFailedError(ValueError):
    """A request is valid but cannot proceed yet (e.g. the portfolio is empty)."""

    def __init__(self, code: str, hint: str):
        super().__init__(hint)
        self.code = code
        self.hint = hint
