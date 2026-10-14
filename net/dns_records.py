"""Real DNS lookups for email-authentication records. Returns None when a lookup could not be completed,
so callers can distinguish 'record absent' (empty list) from 'could not check' (None)."""

from typing import List, Optional

import dns.exception
import dns.resolver

from net.validate import is_valid_hostname

_TIMEOUT = 4.0


def lookup_txt(name: str) -> Optional[List[str]]:
    if not is_valid_hostname(name):
        return None
    resolver = dns.resolver.Resolver()
    resolver.lifetime = _TIMEOUT
    try:
        answers = resolver.resolve(name, "TXT")
    except (dns.resolver.NXDOMAIN, dns.resolver.NoAnswer):
        return []
    except (dns.exception.DNSException, OSError):
        return None
    return ["".join(part.decode("utf-8", "replace") for part in rdata.strings) for rdata in answers]


def lookup_mx(domain: str) -> Optional[List[str]]:
    if not is_valid_hostname(domain):
        return None
    resolver = dns.resolver.Resolver()
    resolver.lifetime = _TIMEOUT
    try:
        answers = resolver.resolve(domain, "MX")
    except (dns.resolver.NXDOMAIN, dns.resolver.NoAnswer):
        return []
    except (dns.exception.DNSException, OSError):
        return None
    return [str(r.exchange).rstrip(".") for r in sorted(answers, key=lambda r: r.preference)]


def lookup_cname(name: str) -> Optional[List[str]]:
    if not is_valid_hostname(name):
        return None
    resolver = dns.resolver.Resolver()
    resolver.lifetime = _TIMEOUT
    try:
        answers = resolver.resolve(name, "CNAME")
    except (dns.resolver.NXDOMAIN, dns.resolver.NoAnswer):
        return []
    except (dns.exception.DNSException, OSError):
        return None
    return [str(r.target).rstrip(".") for r in answers]
