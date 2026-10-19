"""
EvidenceLedger: Provenance, Facts, Inferences, and Unknown Tracking System.

Inspired by REA (Reverse Engineer Anything) architecture:
Separates:
  - Observations: Raw bytes, HTTP status codes, raw MX responses, DOM tags.
  - Derivations: Normalized metrics, hashes (Gravatar, SHA-256), LCP timings.
  - Inferences: Statistical models, Bayesian P(Close), predicted deal ACV.
  - Unknowns: Explicitly tracked missing knowledge with tagged reason codes.
"""

import hashlib
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


class EvidenceRecord:
    """
    Immutable representation of an investigation finding with explicit provenance.
    """

    def __init__(
        self,
        evidence_id: str,
        target_domain: str,
        operation: str,
        timestamp: str,
        observations: Dict[str, Any],
        derivations: Dict[str, Any],
        inferences: Dict[str, Any],
        unknowns: List[Dict[str, str]],
        limitations: List[str],
        confidence_score: float
    ):
        self.evidence_id = evidence_id
        self.target_domain = target_domain
        self.operation = operation
        self.timestamp = timestamp
        self.observations = observations or {}
        self.derivations = derivations or {}
        self.inferences = inferences or {}
        self.unknowns = unknowns or []
        self.limitations = limitations or []
        self.confidence_score = max(0.0, min(1.0, float(confidence_score)))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "evidence_id": self.evidence_id,
            "target_domain": self.target_domain,
            "operation": self.operation,
            "timestamp": self.timestamp,
            "observations": self.observations,
            "derivations": self.derivations,
            "inferences": self.inferences,
            "unknowns": self.unknowns,
            "limitations": self.limitations,
            "confidence_score": self.confidence_score
        }

    def compute_sha256(self) -> str:
        """Computes cryptographic digest of the record content."""
        canonical = json.dumps(self.to_dict(), sort_keys=True)
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


class EvidenceLedger:
    """
    Queryable storage for audit evidence records, maintaining historical provenance
    and supporting differential comparison without hallucinations.
    """

    def __init__(self, storage_dir: Optional[str] = None):
        self.storage_dir = Path(storage_dir or os.path.join("data", "evidence"))
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self._memory_cache: Dict[str, EvidenceRecord] = {}

    def record_evidence(
        self,
        target_domain: str,
        operation: str,
        observations: Optional[Dict[str, Any]] = None,
        derivations: Optional[Dict[str, Any]] = None,
        inferences: Optional[Dict[str, Any]] = None,
        unknowns: Optional[List[Dict[str, str]]] = None,
        limitations: Optional[List[str]] = None,
        confidence_score: float = 0.90
    ) -> EvidenceRecord:
        """
        Creates, seals, and persists an immutable EvidenceRecord.
        """
        domain_clean = (target_domain or "unknown").strip().lower()
        now_iso = datetime.now(timezone.utc).isoformat()
        
        seed = f"{domain_clean}:{operation}:{now_iso}:{time.time_ns()}"
        evidence_id = f"ev_{hashlib.sha256(seed.encode('utf-8')).hexdigest()[:16]}"

        record = EvidenceRecord(
            evidence_id=evidence_id,
            target_domain=domain_clean,
            operation=operation,
            timestamp=now_iso,
            observations=observations or {},
            derivations=derivations or {},
            inferences=inferences or {},
            unknowns=unknowns or [],
            limitations=limitations or [],
            confidence_score=confidence_score
        )

        self._memory_cache[evidence_id] = record
        
        # Persist to disk for long-term audit trail
        target_file = self.storage_dir / f"{evidence_id}.json"
        with open(target_file, "w", encoding="utf-8") as f:
            json.dump(record.to_dict(), f, indent=2)

        return record

    def get_evidence(self, evidence_id: str) -> Optional[EvidenceRecord]:
        """Retrieves an evidence record by ID from memory or disk."""
        if evidence_id in self._memory_cache:
            return self._memory_cache[evidence_id]

        target_file = self.storage_dir / f"{evidence_id}.json"
        if target_file.exists():
            try:
                with open(target_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                rec = EvidenceRecord(**data)
                self._memory_cache[evidence_id] = rec
                return rec
            except Exception:
                return None
        return None

    def list_unknowns_for_domain(self, domain: str) -> List[Dict[str, Any]]:
        """Returns all open unknowns across audits for a target domain."""
        domain_clean = domain.strip().lower()
        results: List[Dict[str, Any]] = []
        for rec in self._memory_cache.values():
            if rec.target_domain == domain_clean and rec.unknowns:
                results.extend(rec.unknowns)
        return results

    def compare_evidence(self, ev_id_a: str, ev_id_b: str) -> Dict[str, Any]:
        """
        Semantic differential comparison between two evidence records.
        Distinguishes confirmed differences from unknown/missing facets.
        """
        rec_a = self.get_evidence(ev_id_a)
        rec_b = self.get_evidence(ev_id_b)

        if not rec_a or not rec_b:
            return {
                "status": "error",
                "error": "One or both evidence IDs not found in ledger"
            }

        # 1. Compare Derivations (e.g. LCP latency, DOM size)
        metric_diffs: Dict[str, Any] = {}
        all_metric_keys = set(rec_a.derivations.keys()) | set(rec_b.derivations.keys())
        for k in all_metric_keys:
            val_a = rec_a.derivations.get(k)
            val_b = rec_b.derivations.get(k)
            if val_a is None or val_b is None:
                metric_diffs[k] = {
                    "comparison": "incomparable_facet_missing",
                    "val_a": val_a,
                    "val_b": val_b
                }
            elif isinstance(val_a, (int, float)) and isinstance(val_b, (int, float)):
                metric_diffs[k] = {
                    "comparison": "delta",
                    "delta": round(val_b - val_a, 3),
                    "val_a": val_a,
                    "val_b": val_b,
                    "ratio": round(val_b / val_a, 2) if val_a != 0 else None
                }
            else:
                metric_diffs[k] = {
                    "comparison": "exact_match" if val_a == val_b else "different",
                    "val_a": val_a,
                    "val_b": val_b
                }

        # 2. Compare Inferences (e.g. P(Close), ACV)
        inference_diffs: Dict[str, Any] = {}
        all_inf_keys = set(rec_a.inferences.keys()) | set(rec_b.inferences.keys())
        for k in all_inf_keys:
            val_a = rec_a.inferences.get(k)
            val_b = rec_b.inferences.get(k)
            if isinstance(val_a, (int, float)) and isinstance(val_b, (int, float)):
                inference_diffs[k] = {
                    "delta": round(val_b - val_a, 3),
                    "val_a": val_a,
                    "val_b": val_b
                }
            else:
                inference_diffs[k] = {"val_a": val_a, "val_b": val_b}

        return {
            "status": "success",
            "evidence_a": {"id": rec_a.evidence_id, "domain": rec_a.target_domain, "timestamp": rec_a.timestamp},
            "evidence_b": {"id": rec_b.evidence_id, "domain": rec_b.target_domain, "timestamp": rec_b.timestamp},
            "metric_differential": metric_diffs,
            "inference_differential": inference_diffs,
            "open_unknowns_a": rec_a.unknowns,
            "open_unknowns_b": rec_b.unknowns
        }
