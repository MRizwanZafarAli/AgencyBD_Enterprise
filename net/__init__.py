"""Net package for SSRF-safe network requests."""
from net.fetcher import SafeFetcher, SSRFSecurityError

__all__ = ["SafeFetcher", "SSRFSecurityError"]
