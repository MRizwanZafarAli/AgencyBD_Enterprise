"""
Agency Portfolio & Proof Library.

The only source of "what we have done" that proposals may cite. Assets are entered by the agency
(case studies with real metrics). Retrieval is deterministic TF-IDF cosine similarity, so results are
explainable and need no embedding service.
"""

import json
import math
import re
from collections import Counter
from typing import Any, Dict, List, Optional, Tuple


from database.db import get_db

_WORD = re.compile(r"[a-z0-9][a-z0-9+#.\-]{2,}")
_STOP = {"the", "and", "for", "with", "that", "this", "our", "you", "your", "are", "from", "have", "will", "can", "has",
         "was", "were", "their", "into", "about", "more", "than", "how", "what", "when", "which", "need", "looking"}


def _tokens(text: str) -> List[str]:
    return [w for w in _WORD.findall((text or "").lower()) if w not in _STOP]


def _asset_text(asset: Dict[str, Any]) -> str:
    parts = [asset.get("title", ""), asset.get("industry", "") or "", asset.get("body", ""),
             " ".join(asset.get("services") or []), " ".join(asset.get("tech") or [])]
    return " ".join(parts)


def _row_to_asset(row) -> Dict[str, Any]:
    d = dict(row)
    d["services"] = json.loads(d.pop("services_json", None) or "[]")
    d["tech"] = json.loads(d.pop("tech_json", None) or "[]")
    d["metrics"] = json.loads(d.pop("metrics_json", None) or "{}")
    return d


class PortfolioLibrary:
    @staticmethod
    def add_asset(org_id: str, title: str, body: str, industry: Optional[str] = None, services: Optional[List[str]] = None,
                  tech: Optional[List[str]] = None, metrics: Optional[Dict[str, Any]] = None,
                  source_url: Optional[str] = None) -> Dict[str, Any]:
        if not title.strip() or len(body.split()) < 15:
            raise ValueError("A case study needs a title and a body of at least 15 words describing what was done and the result.")
        with get_db() as conn:
            cur = conn.execute(
                "INSERT INTO portfolio_assets (org_id, title, industry, services_json, tech_json, metrics_json, body, source_url) "
                "VALUES (?,?,?,?,?,?,?,?)",
                (org_id, title.strip(), industry, json.dumps(services or []), json.dumps(tech or []),
                 json.dumps(metrics or {}), body.strip(), source_url))
            conn.commit()
            row = conn.execute("SELECT * FROM portfolio_assets WHERE id = ?", (cur.lastrowid,)).fetchone()
            return _row_to_asset(row)

    @staticmethod
    def list_assets(org_id: str) -> List[Dict[str, Any]]:
        with get_db() as conn:
            rows = conn.execute("SELECT * FROM portfolio_assets WHERE org_id = ? ORDER BY id DESC", (org_id,)).fetchall()
            return [_row_to_asset(r) for r in rows]

    @staticmethod
    def delete_asset(org_id: str, asset_id: int) -> bool:
        with get_db() as conn:
            cur = conn.execute("DELETE FROM portfolio_assets WHERE id = ? AND org_id = ?", (asset_id, org_id))
            conn.commit()
            return cur.rowcount > 0

    @classmethod
    def search(cls, org_id: str, query: str, k: int = 3, min_score: float = 0.05) -> List[Tuple[Dict[str, Any], float]]:
        """Returns up to k (asset, score) pairs whose text overlaps the query; empty if nothing is relevant."""
        assets = cls.list_assets(org_id)
        if not assets:
            return []
        docs = [Counter(_tokens(_asset_text(a))) for a in assets]
        df = Counter(t for d in docs for t in d)
        n = len(docs)
        idf = {t: math.log((1 + n) / (1 + c)) + 1.0 for t, c in df.items()}
        q = Counter(_tokens(query))

        def vec(counter):
            return {t: (1 + math.log(c)) * idf.get(t, 1.0) for t, c in counter.items()}

        qv = vec(q)
        qnorm = math.sqrt(sum(v * v for v in qv.values())) or 1.0
        scored = []
        for asset, doc in zip(assets, docs):
            dv = vec(doc)
            dnorm = math.sqrt(sum(v * v for v in dv.values())) or 1.0
            dot = sum(qv[t] * dv.get(t, 0.0) for t in qv)
            scored.append((asset, dot / (qnorm * dnorm)))
        scored.sort(key=lambda x: x[1], reverse=True)
        return [(a, s) for a, s in scored[:k] if s >= min_score]
