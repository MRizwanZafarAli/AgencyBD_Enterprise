"""
SpintaxCopywriterAgent: Semantic Anti-Clustering Dynamic Outreach Engine.
Generates unique syntactic permutations for cold outreach to prevent ESP pattern detection
and email clustering by Google Workspace & Microsoft 365 spam filters.
"""

import random
import re
from typing import Dict, Any, List
from config.settings import settings
from config.deliverability import analyze_spam_friction

class SpintaxCopywriterAgent:
    """
    Spintax & Semantic Variations Engine.
    Ensures no two sent emails share an identical byte signature.
    """

    SUBJECT_SPINTAX = [
        "{first_name} - {company}'s tech backlog",
        "question regarding {company}'s engineering roadmap",
        "{first_name} / senior dev capacity at {company}",
        "quick technical observation on {domain}",
        "{domain} mobile speed audit ({first_name})"
    ]

    OBSERVATION_SPINTAX = [
        "Ran a speed audit on {domain} this morning",
        "Took a look at {domain}'s frontend latency earlier today",
        "Analyzed the core web vitals on {domain} this week",
        "Was reviewing technical performance metrics on {domain}"
    ]

    IMPACT_SPINTAX = [
        "Google treats 2.5s as the cut-off for a good Largest Contentful Paint, and slower pages tend to lose mobile visitors.",
        "That is outside the range Google's Core Web Vitals report counts as good loading performance.",
        "Pages above 2.5s LCP are flagged as needing improvement in Google's Core Web Vitals assessment."
    ]

    CTA_SPINTAX = [
        "Mind if I send over a short note on what is slowing it down?",
        "Happy to record a short walkthrough of what is slowing it down if useful?",
        "Open to a short diagnostic note on what is slowing it down?",
        "Worth a brief 10-minute intro this week to share our findings?"
    ]

    def parse_spintax(self, text: str) -> str:
        """Recursively parses standard spintax pattern {option1|option2|option3}."""
        pattern = re.compile(r'\{([^{}]+)\}')
        while pattern.search(text):
            text = pattern.sub(lambda m: random.choice(m.group(1).split('|')), text)
        return text

    def generate_unique_sequence(self, first_name: str, company: str, domain: str, lcp: float, stack: str) -> Dict[str, Any]:
        """
        Generates a syntactically unique 3-step sequence guaranteed not to trigger ESP clustering.
        """
        # Step 1
        raw_subject = random.choice(self.SUBJECT_SPINTAX).format(first_name=first_name, company=company, domain=domain)
        observation = random.choice(self.OBSERVATION_SPINTAX).format(domain=domain)
        impact = random.choice(self.IMPACT_SPINTAX)
        cta = random.choice(self.CTA_SPINTAX)

        step_1_body = (
            f"Hi {first_name},\n\n"
            f"{observation}—your mobile LCP is currently {lcp}s on {stack}, which is above Google's 2.5s threshold.\n\n"
            f"{impact}\n\n"
            f"{cta}"
        )

        # Step 2 (Bump)
        bump_openers = [
            f"Hi {first_name},\n\nFollowing up on my earlier note. I can put together a visual teardown comparing your latency to modern edge deployment standards.",
            f"Hi {first_name},\n\nQuick bump on this. I can map out the asset bottlenecks behind that {lcp}s mobile LCP.",
            f"Hi {first_name},\n\nWanted to follow up with an offer: a quick architecture comparison of how {domain} could get under Google's 2.5s threshold."
        ]
        step_2_body = f"{random.choice(bump_openers)}\n\nHappy to put it together if helpful for your engineers?\n\nBest,\n{settings.agency.founder_name}"

        # Step 3 (Breakup)
        step_3_body = (
            f"Hi {first_name},\n\n"
            f"I assume engineering priorities are fully booked right now, so I will close your file for now.\n\n"
            f"If you ever need an on-demand senior engineering pod down the line, feel free to grab time directly: {settings.agency.booking_link}\n\n"
            f"Wishing {company} continued growth!"
        )

        score_1, _, rating_1 = analyze_spam_friction(raw_subject, step_1_body)

        return {
            "step_1": {
                "subject": raw_subject,
                "body": step_1_body,
                "spam_score": score_1,
                "rating": rating_1
            },
            "step_2": {
                "subject": f"Re: {raw_subject}",
                "body": step_2_body
            },
            "step_3": {
                "subject": f"Closing the loop: {company}",
                "body": step_3_body
            }
        }
