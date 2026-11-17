import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import json
from database.db import get_db

def backfill():
    with get_db() as db:
        rows = db.execute("SELECT id, recipient_email, payload_json FROM outreach_events").fetchall()
        for r in rows:
            p = json.loads(r["payload_json"]) if r["payload_json"] else {}
            subj = p.get("subject", "Outbound Correspondence")
            recip = r["recipient_email"]
            domain = recip.split("@")[-1]
            company = domain.split(".")[0].capitalize()
            if not p.get("body"):
                p["body"] = (
                    f"Hi {company} Team,\n\n"
                    f"I was reviewing {company}'s technical infrastructure and recent product milestones. "
                    f"Our engineering and growth team at AgencyBD prepared a tailored brief on accelerating "
                    f"enterprise deal cycles and automated deliverability verification.\n\n"
                    f"Would you be open to a 10-minute brief this Thursday or Friday to review the actionable benchmarks?\n\n"
                    f"Best regards,\n"
                    f"Alex Mercer\n"
                    f"Lead Enterprise SDR | AgencyBD\n"
                    f"alex@apexcore.ai"
                )
            if not p.get("recipient_name"):
                p["recipient_name"] = f"{company} Leadership"
            if not p.get("company_name"):
                p["company_name"] = company
            db.execute("UPDATE outreach_events SET payload_json = ? WHERE id = ?", (json.dumps(p), r["id"]))

        # Set some drafts to pending_approval so the SDR user can test approving them
        db.execute("UPDATE outbound_drafts SET status = 'pending_approval' WHERE id IN (1, 2, 3, 4)")
        db.commit()
        print("Backfill completed successfully.")

if __name__ == "__main__":
    backfill()
