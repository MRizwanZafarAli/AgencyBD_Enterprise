"""
Passive technology fingerprinting: which software and versions does a site reveal to ANY visitor?

Sources: response headers (Server, X-Powered-By), the generator meta tag, WordPress version query strings on core files, and
versioned library URLs (cdnjs, jsDelivr, unpkg, local filenames such as jquery-3.3.1.min.js). Nothing is probed; only the
homepage response we already hold is read. A version seen here is a CLAIM by the server or page, and can be hidden, spoofed or
backported, so each result carries a confidence and the exact signal.
"""

import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional

DISTRO = re.compile(r"\((ubuntu|debian|centos|red hat|rhel|rocky|alma|suse|amazon|fedora)[^)]*\)", re.IGNORECASE)

# product -> how to look it up. cpe: NVD CPE vendor:product pairs to try. osv: (ecosystem, package) for library advisories.
PRODUCTS: Dict[str, Dict] = {
    "php": {"cpe": [("php", "php")], "label": "PHP"},
    "nginx": {"cpe": [("f5", "nginx"), ("nginx", "nginx")], "label": "nginx"},
    "apache": {"cpe": [("apache", "http_server")], "label": "Apache HTTP Server"},
    "iis": {"cpe": [("microsoft", "internet_information_services")], "label": "Microsoft IIS"},
    "wordpress": {"cpe": [("wordpress", "wordpress")], "label": "WordPress"},
    "drupal": {"cpe": [("drupal", "drupal")], "label": "Drupal"},
    "joomla": {"cpe": [("joomla", "joomla\\!")], "label": "Joomla"},
    "jquery": {"osv": ("npm", "jquery"), "label": "jQuery"},
    "bootstrap": {"osv": ("npm", "bootstrap"), "label": "Bootstrap"},
    "lodash": {"osv": ("npm", "lodash"), "label": "lodash"},
    "moment": {"osv": ("npm", "moment"), "label": "Moment.js"},
    "angularjs": {"osv": ("npm", "angular"), "label": "AngularJS"},
    "vue": {"osv": ("npm", "vue"), "label": "Vue"},
    "react": {"osv": ("npm", "react"), "label": "React"},
}
CDN_NAMES = {"jquery": "jquery", "twitter-bootstrap": "bootstrap", "bootstrap": "bootstrap", "lodash.js": "lodash", "lodash": "lodash",
             "moment.js": "moment", "moment": "moment", "angular.js": "angularjs", "angularjs": "angularjs", "vue": "vue", "react": "react"}


@dataclass
class Tech:
    product: str
    version: str
    signal: str                     # human-readable: where it was seen
    source: str                     # header | meta | asset
    backport_risk: bool = False     # distro builds often patch without changing the version string
    confidence: float = 0.8
    extra: Dict[str, str] = field(default_factory=dict)

    @property
    def label(self) -> str:
        return PRODUCTS[self.product]["label"]


def _add(found: List[Tech], t: Tech) -> None:
    if t.product in PRODUCTS and not any(x.product == t.product and x.version == t.version for x in found):
        found.append(t)


def fingerprint(headers: Dict[str, str], html: str) -> List[Tech]:
    h = {k.lower(): v for k, v in (headers or {}).items()}
    found: List[Tech] = []

    server = h.get("server", "")
    m = re.search(r"\b(nginx|apache|microsoft-iis)/(\d+(?:\.\d+){1,3})", server, re.IGNORECASE)
    if m:
        product = {"microsoft-iis": "iis"}.get(m.group(1).lower(), m.group(1).lower())
        backport = bool(DISTRO.search(server))
        _add(found, Tech(product, m.group(2), f"Server header: {server}", "header", backport, 0.4 if backport else 0.7))

    powered = h.get("x-powered-by", "")
    m = re.search(r"\bPHP/(\d+(?:\.\d+){1,3})", powered + " " + server, re.IGNORECASE)
    if m:
        backport = bool(DISTRO.search(server))
        _add(found, Tech("php", m.group(1), f"X-Powered-By header: {powered or server}", "header", backport, 0.4 if backport else 0.7))

    body = html or ""
    for name, pat in (("wordpress", r'<meta[^>]+name=["\']generator["\'][^>]+content=["\']WordPress (\d+(?:\.\d+){1,2})'),
                      ("drupal", r'<meta[^>]+name=["\']generator["\'][^>]+content=["\']Drupal (\d+(?:\.\d+)?)'),
                      ("joomla", r'<meta[^>]+name=["\']generator["\'][^>]+content=["\']Joomla! (\d+(?:\.\d+){1,2})')):
        m = re.search(pat, body, re.IGNORECASE)
        if m:
            _add(found, Tech(name, m.group(1), f"generator meta tag: {m.group(0)[-40:]}", "meta", False, 0.75))
    m = re.search(r"/wp-(?:includes/js/wp-emoji-release\.min\.js|includes/css/dist/block-library/style\.min\.css)\?ver=(\d+\.\d+(?:\.\d+)?)", body)
    if m:
        _add(found, Tech("wordpress", m.group(1), "WordPress core file version query string", "asset", False, 0.8))

    # versioned libraries in script/link URLs
    for url in re.findall(r'(?:src|href)=["\']([^"\']+\.js[^"\']*)["\']', body, re.IGNORECASE):
        m = re.search(r"cdnjs\.cloudflare\.com/ajax/libs/([\w.-]+)/(\d+\.\d+\.\d+)/", url)
        if not m:
            m = re.search(r"(?:cdn\.jsdelivr\.net/npm|unpkg\.com)/(@?[\w./-]+?)@(\d+\.\d+\.\d+)", url)
        if m:
            name = CDN_NAMES.get(m.group(1).lower())
            if name:
                _add(found, Tech(name, m.group(2), f"script URL: {url[:90]}", "asset", False, 0.9))
            continue
        m = re.search(r"/(jquery|bootstrap|lodash|moment)[-.]v?(\d+\.\d+\.\d+)(?:\.min)?\.js", url, re.IGNORECASE)
        if m:
            _add(found, Tech(m.group(1).lower(), m.group(2), f"script file name: {url[:90]}", "asset", False, 0.9))
    return found
