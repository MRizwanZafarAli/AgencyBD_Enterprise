"""
MarketIntelligenceAgent: AI-Driven Global Market Sourcing & Geo Recommender.
Analyzes project requirements and service offerings, synthesizes recent enterprise market research
(capital flows, regulatory mandates, tech modernization cycles), and recommends precision geographic targets.
"""

import re
from typing import Dict, Any, List, Optional
from data.geo_database import GeoDatabase, GLOBAL_GEO_REGISTRY

# Recent Market Research Knowledge Base (2025/2026 Enterprise Cycles)
MARKET_RESEARCH_VECTORS = {
    "ai_agent_rag": {
        "keywords": ["ai", "llm", "agent", "rag", "langchain", "autonomous", "machine learning", "nlp", "deep learning"],
        "recommended_geos": [
            {"country": "United States", "state": "California", "cities": ["San Francisco", "Palo Alto", "San Jose"], "score": 98, "rationale": "Global epicenter of Foundation Model and Agentic AI venture funding; companies eager for production-grade agent implementation."},
            {"country": "United States", "state": "New York", "cities": ["New York City", "Brooklyn"], "score": 95, "rationale": "Wall Street and Enterprise media firms adopting private LLM workflows with strict data residency requirements."},
            {"country": "United Kingdom", "state": "Greater London", "cities": ["London", "Shoreditch"], "score": 92, "rationale": "Leading European AI hub with DeepMind ecosystem; strong demand for generative AI in legal and insurance sectors."},
            {"country": "France", "state": "Île-de-France", "cities": ["Paris", "Station F"], "score": 90, "rationale": "Massive capital inflows post-Mistral AI; French enterprise champions investing in European sovereign AI stacks."},
            {"country": "United Arab Emirates", "state": "Dubai", "cities": ["Dubai (DIFC)"], "score": 93, "rationale": "UAE Sovereign AI strategy & Minister of AI initiatives allocating multi-million dollar contracts for GovTech and enterprise automation."}
        ],
        "compliance_hooks": ["SOC2 Type II data boundary", "Zero-training data retention agreements", "EU AI Act high-risk classification compliance"],
        "job_hiring_triggers": ["AI Engineer", "LLM Architect", "Machine Learning Lead", "Head of Data Science"]
    },
    "fintech_banking": {
        "keywords": ["fintech", "banking", "payments", "pci", "crypto", "trading", "wealth", "insurtech", "lending"],
        "recommended_geos": [
            {"country": "United States", "state": "New York", "cities": ["New York City"], "score": 97, "rationale": "Concentration of Tier-1 investment banks, hedge funds, and Series B+ fintechs replacing legacy core banking monoliths."},
            {"country": "United Kingdom", "state": "Greater London", "cities": ["London", "Canary Wharf"], "score": 96, "rationale": "World's most active open-banking and international remittance hub; high willingness to pay for sub-second execution APIs."},
            {"country": "Switzerland", "state": "Zurich", "cities": ["Zurich", "Zug"], "score": 94, "rationale": "Private wealth management, secure custody, and institutional Web3/Crypto Valley capital; premium contract sizes ($150k+)."},
            {"country": "Singapore", "state": "Singapore", "cities": ["Singapore (CBD)"], "score": 93, "rationale": "Monetary Authority of Singapore (MAS) sandbox environment driving cross-border B2B payment infrastructure overhauls."},
            {"country": "Germany", "state": "Hesse", "cities": ["Frankfurt"], "score": 91, "rationale": "European Central Bank jurisdiction; ongoing EU DORA (Digital Operational Resilience Act) compliance enforcement deadlines."}
        ],
        "compliance_hooks": ["EU DORA operational resilience audit", "PCI-DSS v4.0 tokenization requirements", "SEC Rule 17a-4 audit logging"],
        "job_hiring_triggers": ["Senior Backend MTA Engineer", "Payments Infrastructure Architect", "Compliance Systems Engineer"]
    },
    "ecommerce_speed": {
        "keywords": ["ecommerce", "shopify", "headless", "magento", "woocommerce", "retail", "dtc", "conversion", "store"],
        "recommended_geos": [
            {"country": "United States", "state": "California", "cities": ["Los Angeles", "Irvine"], "score": 95, "rationale": "Highest density of high-revenue direct-to-consumer (DTC) beauty, apparel, and lifestyle brands losing 7-figures to sluggish mobile checkout."},
            {"country": "United States", "state": "Florida", "cities": ["Miami", "Fort Lauderdale"], "score": 90, "rationale": "Surging DTC brand relocations; rapid expansion into omnichannel retail demanding headless Next.js architecture."},
            {"country": "United Kingdom", "state": "Greater Manchester", "cities": ["Manchester", "Salford"], "score": 89, "rationale": "UK fast-fashion and eCommerce capital (Boohoo/THG cluster); heavy pressure to improve mobile Core Web Vitals (INP and LCP)."},
            {"country": "Netherlands", "state": "North Holland", "cities": ["Amsterdam"], "score": 91, "rationale": "Pan-European digital commerce champions; stringent consumer protection laws and emphasis on ultra-low latency checkout."}
        ],
        "compliance_hooks": ["Google INP (Interaction to Next Paint) SEO penalties", "Checkout abandonment recovery through sub-second TTFB", "Omnichannel ERP headless sync"],
        "job_hiring_triggers": ["Head of eCommerce", "Shopify Plus Architect", "VP of Digital Growth"]
    },
    "healthtech_hipaa": {
        "keywords": ["health", "healthcare", "hipaa", "medical", "clinic", "biotech", "pharma", "patient", "telehealth"],
        "recommended_geos": [
            {"country": "United States", "state": "Massachusetts", "cities": ["Boston", "Cambridge"], "score": 98, "rationale": "Top global cluster for Life Sciences, clinical research, and hospital systems modernizing EHR integrations."},
            {"country": "United States", "state": "California", "cities": ["San Diego", "San Francisco"], "score": 94, "rationale": "Telehealth and medical device companion app startups scaling under tight FDA and HIPAA cybersecurity scrutiny."},
            {"country": "United States", "state": "North Carolina", "cities": ["Raleigh", "Durham"], "score": 90, "rationale": "Research Triangle Park (RTP) clinical trials data exchange; high demand for zero-trust HIPAA compliant portal architectures."},
            {"country": "Switzerland", "state": "Vaud", "cities": ["Lausanne"], "score": 91, "rationale": "Health Valley corridor; European pharmaceutical headquarters investing in secure patient analytics."}
        ],
        "compliance_hooks": ["HIPAA Omnibus Rule Business Associate Agreement (BAA)", "HL7 FHIR Interoperability Standard", "FDA 21 CFR Part 11 electronic audit trail"],
        "job_hiring_triggers": ["HealthTech Product Lead", "FHIR Integration Specialist", "Clinical Systems Director"]
    },
    "legacy_cloud_modernization": {
        "keywords": ["modernization", "refactor", "legacy", "migration", "cloud", "aws", "microservices", "devops", "kubernetes", "php", "wordpress"],
        "recommended_geos": [
            {"country": "United States", "state": "Texas", "cities": ["Austin", "Dallas", "Houston"], "score": 96, "rationale": "Booming corporate headquarters relocation corridor; massive enterprise mid-market firms migrating 10-year-old monoliths to modern AWS/FastAPI stacks."},
            {"country": "United States", "state": "Illinois", "cities": ["Chicago", "Naperville"], "score": 92, "rationale": "Industrial, logistics, and trading firms saddled with technical debt and high cloud hosting overheads."},
            {"country": "Germany", "state": "Bavaria", "cities": ["Munich", "Nuremberg"], "score": 93, "rationale": "Mittelstand industrial champions digitizing manufacturing processes into cloud-native microservices."},
            {"country": "Canada", "state": "Ontario", "cities": ["Toronto", "Waterloo"], "score": 91, "rationale": "Canadian enterprise software hub with federal digital transformation grants subsidizing modernization sprints."}
        ],
        "compliance_hooks": ["40-60% cloud compute cost reduction via containerization", "Zero-downtime database schema migration", "SOC2 and ISO 27001 posture hardening"],
        "job_hiring_triggers": ["VP Engineering", "Cloud Migration Architect", "Director of Infrastructure"]
    }
}

class MarketIntelligenceAgent:
    """
    Synthesizes project demand against global geographic research to recommend
    high-converting markets, target titles, boolean search queries, and regulatory hooks.
    """

    def analyze_demand(
        self,
        project_demand: str,
        ticket_size: str = "$25k-$75k",
        target_countries: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        demand_lower = project_demand.lower()

        # 1. Match primary industry/technical vector
        matched_vector_key = "legacy_cloud_modernization"
        max_matches = 0

        for vector_key, data in MARKET_RESEARCH_VECTORS.items():
            matches = sum(1 for kw in data["keywords"] if kw in demand_lower)
            if matches > max_matches:
                max_matches = matches
                matched_vector_key = vector_key

        vector_data = MARKET_RESEARCH_VECTORS[matched_vector_key]

        # 2. Filter or rank recommended geos
        recommended_geos = vector_data["recommended_geos"]
        if target_countries:
            filtered = [g for g in recommended_geos if g["country"] in target_countries]
            if filtered:
                recommended_geos = filtered

        # 3. Generate precise operational queries for the agents
        primary_geo = recommended_geos[0]
        country = primary_geo["country"]
        state = primary_geo["state"]
        primary_city = primary_geo["cities"][0]

        # Sourcing Query Generators
        if matched_vector_key == "ai_agent_rag":
            niche_title = "Artificial Intelligence Software"
            gmaps_query = f"AI Software Company in {primary_city}, {state}"
            linkedin_boolean = f'site:linkedin.com/in/ ("VP of Engineering" OR "CTO" OR "Head of AI") "{primary_city}"'
            jobspy_query = "AI Engineer OR Machine Learning"
        elif matched_vector_key == "fintech_banking":
            niche_title = "FinTech & Financial Software"
            gmaps_query = f"Fintech Company in {primary_city}"
            linkedin_boolean = f'site:linkedin.com/in/ ("Chief Technology Officer" OR "VP Engineering" OR "Head of Payments") "{primary_city}"'
            jobspy_query = "FinTech Software Engineer"
        elif matched_vector_key == "ecommerce_speed":
            niche_title = "E-Commerce Brands & D2C"
            gmaps_query = f"eCommerce Brands in {primary_city}, {state}"
            linkedin_boolean = f'site:linkedin.com/in/ ("Head of eCommerce" OR "VP Digital" OR "Chief Marketing Officer") "{primary_city}"'
            jobspy_query = "Shopify Developer OR eCommerce Engineer"
        elif matched_vector_key == "healthtech_hipaa":
            niche_title = "HealthTech & Telehealth"
            gmaps_query = f"HealthTech Software Company in {primary_city}, {state}"
            linkedin_boolean = f'site:linkedin.com/in/ ("CTO" OR "VP Engineering" OR "Chief Medical Officer") "{primary_city}"'
            jobspy_query = "HealthTech Engineer OR HIPAA"
        else:
            niche_title = "Enterprise Software & Cloud"
            gmaps_query = f"Software Development Company in {primary_city}, {state}"
            linkedin_boolean = f'site:linkedin.com/in/ ("CTO" OR "VP Engineering" OR "Director of Software") "{primary_city}"'
            jobspy_query = "Software Engineer OR Cloud Architect"

        return {
            "project_demand_input": project_demand,
            "detected_market_sector": niche_title,
            "matched_research_vector": matched_vector_key,
            "ticket_size": ticket_size,
            "top_recommended_geos": recommended_geos,
            "primary_target": {
                "country": country,
                "state_province": state,
                "city": primary_city,
                "opportunity_score": primary_geo["score"],
                "strategic_rationale": primary_geo["rationale"]
            },
            "operational_search_queries": {
                "google_maps_query": gmaps_query,
                "google_maps_location": f"{primary_city}, {state}, {country}",
                "jobspy_hiring_trigger": jobspy_query,
                "linkedin_xray_boolean": linkedin_boolean,
                "recommended_titles": vector_data["job_hiring_triggers"]
            },
            "regulatory_attack_angles": vector_data["compliance_hooks"],
            "market_research_summary": (
                f"Based on current enterprise budget allocations for {niche_title}, "
                f"{primary_city} ({state}, {country}) represents the highest-converting territory. "
                f"{primary_geo['rationale']} Target outbound sequences utilizing "
                f"the '{vector_data['compliance_hooks'][0]}' friction hook for peak response rates."
            )
        }
