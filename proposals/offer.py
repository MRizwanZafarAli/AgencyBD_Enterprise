"""A one-page fixed-price offer built from a completed website check and your own service catalog.

Everything in it is either measured (the findings), written by you (offer text, price bands, proof) or an explicit blank that you fill in.
Prices are never invented and never added up for you: if a service has no price band the offer shows a clear blank and lists it under `needs`."""

from datetime import datetime, timezone
from typing import Any, Dict, List

from config.honesty import PreconditionFailedError
from config.settings import settings
from database.db import get_db
from intel import advisor
from intel.services import ServiceCatalog

MAX_ITEMS = 3
MAX_FINDINGS_PER_ITEM = 3


def build_offer(org_id: str, company_id: int) -> Dict[str, Any]:
    with get_db() as db:
        company = db.execute("SELECT name, domain FROM companies WHERE id = ? AND org_id = ?", (company_id, org_id)).fetchone()
    if not company:
        raise LookupError("Company not found")
    advice = advisor.recommendations(company_id, org_id)               # raises PreconditionFailedError('audit_required') without a completed check
    items = advice["recommendations"][:MAX_ITEMS]
    if not items:
        raise PreconditionFailedError("nothing_to_offer", "The last check found nothing above informational level, so there is nothing honest to sell. Look at the site by hand first.")
    a = settings.agency
    needs: List[str] = []
    lines = [f"# Fixed-price offer for {company['name']}", "",
             f"From {a.name or '[your agency name]'}" + (f", {a.founder_name}" if a.founder_name else "") + f"  ",
             f"Prepared {datetime.now(timezone.utc).strftime('%d %B %Y')} from a check of {company['domain'] or 'your website'} made on {advice['audited_at']}.", ""]
    if not a.name:
        needs.append("Your agency name (Settings > Agency profile).")
    lines += ["## What we found", "", "These were measured on your public website. Nothing was tested intrusively.", ""]
    for n, it in enumerate(items, 1):
        lines += [f"{n}. **{it['service']}**"] + [f"   - {f['finding']}" for f in it["findings"][:MAX_FINDINGS_PER_ITEM]]
    lines += ["", "## What we will do, and the price", ""]
    for n, it in enumerate(items, 1):
        svc = ServiceCatalog.get(org_id, it["service_key"])
        what = (svc or {}).get("offer") or None
        price = (svc or {}).get("price_band") or None
        fixes = "; ".join(dict.fromkeys(f["fix"] for f in it["findings"][:MAX_FINDINGS_PER_ITEM] if f.get("fix")))
        if not what:
            needs.append(f"What you would do for {it['service']} (Settings > Services and proof).")
        if not price:
            needs.append(f"Your price for {it['service']} (Settings > Services and proof).")
        lines += [f"{n}. **{it['service']}**: {what or fixes or '[describe the work]'}", f"   - Price: {price or '[your fixed price]'}"]
    lines += ["", "**Total:** [add the total]", "", "## When", "", "[add your delivery time]", ""]
    needs += ["The total (the app does not add price bands for you).", "Your delivery time."]
    proof = (getattr(a, "case_study_metric", None) or "").strip()   # only set when you have also given proof of it
    if proof:
        lines += ["## Recent result", "", proof, ""]
    lines += ["## What is not included", "", "Anything not listed above. Changes beyond this scope are quoted separately before any work starts.", ""]
    if a.booking_link:
        lines += [f"To accept or talk it through: {a.booking_link}", ""]
    else:
        needs.append("A booking link (Settings > Agency profile) so they can say yes in one click.")
    safe = "".join(c if c.isalnum() else "_" for c in company["name"]).strip("_") or "client"
    return {"markdown": "\n".join(lines), "filename": f"Offer_{safe}.md", "needs": needs, "items": len(items)}
