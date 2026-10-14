"""Small helpers shared by connectors."""

import html as htmllib
import re
from typing import List

from bs4 import BeautifulSoup


def clean_html(raw: str, max_len: int = 4000) -> str:
    """HTML (possibly entity-escaped twice, like HN) -> readable text with line breaks."""
    text = htmllib.unescape(raw or "")
    soup = BeautifulSoup(text, "html.parser")
    for br in soup.find_all(["br", "p", "li"]):
        br.insert_before("\n")
    out = re.sub(r"\n{3,}", "\n\n", soup.get_text()).strip()
    return out[:max_len]


def money(text: str) -> List[float]:
    """Dollar/euro/pound amounts mentioned in text, e.g. '$170k to $230k' -> [170000, 230000]."""
    values = []
    for m in re.finditer(r"[$€£]\s?(\d{1,3}(?:,\d{3})+|\d+(?:\.\d+)?)\s?([kKmM])?", text or ""):
        n = float(m.group(1).replace(",", ""))
        n *= {"k": 1_000, "m": 1_000_000}.get((m.group(2) or "").lower(), 1)
        values.append(n)
    return values
