"""
Global Geographic Database: Countries, States/Provinces, and Major Commercial/Tech Cities.
Provides structured geographic hierarchies, purchasing power index, and tech cluster tags
for precision outbound B2B targeting.
"""

from typing import Dict, List, Optional, Any

GLOBAL_GEO_REGISTRY: Dict[str, Dict[str, Any]] = {
    "United States": {
        "code": "US",
        "region": "North America",
        "purchasing_power_tier": "Tier-1",
        "currency": "USD",
        "states_provinces": {
            "California": {
                "cities": ["San Francisco", "San Jose", "Palo Alto", "Los Angeles", "San Diego", "Oakland", "Mountain View", "Sunnyvale", "Irvine"],
                "tech_hub_tags": ["AI/ML", "Enterprise SaaS", "BioTech", "FinTech", "DeepTech"],
                "market_density": "Ultra-High"
            },
            "New York": {
                "cities": ["New York City", "Brooklyn", "Buffalo", "Rochester", "Albany"],
                "tech_hub_tags": ["FinTech", "InsurTech", "AdTech", "HealthTech", "Media"],
                "market_density": "Ultra-High"
            },
            "Texas": {
                "cities": ["Austin", "Dallas", "Houston", "San Antonio", "Fort Worth", "Plano"],
                "tech_hub_tags": ["Cloud Infrastructure", "Enterprise Software", "DefenseTech", "EnergyTech"],
                "market_density": "Very-High"
            },
            "Washington": {
                "cities": ["Seattle", "Bellevue", "Redmond", "Tacoma", "Spokane"],
                "tech_hub_tags": ["Cloud Computing", "AI", "E-Commerce", "Gaming"],
                "market_density": "Very-High"
            },
            "Massachusetts": {
                "cities": ["Boston", "Cambridge", "Worcester", "Waltham", "Somerville"],
                "tech_hub_tags": ["BioTech", "EdTech", "Robotics", "HealthTech", "AI Research"],
                "market_density": "Very-High"
            },
            "Illinois": {
                "cities": ["Chicago", "Naperville", "Evanston", "Schaumburg"],
                "tech_hub_tags": ["FinTech", "LogisticsTech", "ManufacturingTech", "B2B SaaS"],
                "market_density": "High"
            },
            "Colorado": {
                "cities": ["Denver", "Boulder", "Colorado Springs", "Fort Collins"],
                "tech_hub_tags": ["Aerospace", "CleanTech", "SaaS", "Outdoor eCommerce"],
                "market_density": "High"
            },
            "Florida": {
                "cities": ["Miami", "Tampa", "Orlando", "Fort Lauderdale", "Jacksonville"],
                "tech_hub_tags": ["Web3/FinTech", "HealthTech", "HospitalityTech", "RealEstateTech"],
                "market_density": "High"
            },
            "Georgia": {
                "cities": ["Atlanta", "Alpharetta", "Savannah"],
                "tech_hub_tags": ["FinTech (Transaction Alley)", "Cybersecurity", "HealthTech"],
                "market_density": "High"
            },
            "North Carolina": {
                "cities": ["Raleigh", "Durham", "Charlotte", "Cary"],
                "tech_hub_tags": ["Research Triangle BioTech", "FinTech Banking", "Cleantech"],
                "market_density": "High"
            },
            "Utah": {
                "cities": ["Salt Lake City", "Provo", "Lehi (Silicon Slopes)", "Sandy"],
                "tech_hub_tags": ["B2B SaaS", "Cloud Software", "Data Analytics"],
                "market_density": "High"
            },
            "Virginia": {
                "cities": ["Arlington", "McLean", "Reston", "Richmond", "Tysons"],
                "tech_hub_tags": ["GovTech", "Cybersecurity", "Defense AI", "Cloud Data Centers"],
                "market_density": "High"
            },
            "Pennsylvania": {
                "cities": ["Philadelphia", "Pittsburgh", "Allentown"],
                "tech_hub_tags": ["Autonomous Systems", "Robotics", "Health/Pharma"],
                "market_density": "Medium-High"
            },
            "Ohio": {
                "cities": ["Columbus", "Cleveland", "Cincinnati"],
                "tech_hub_tags": ["InsurTech", "SupplyChain", "Manufacturing AI"],
                "market_density": "Medium"
            },
            "Michigan": {
                "cities": ["Detroit", "Ann Arbor", "Grand Rapids"],
                "tech_hub_tags": ["AutoTech", "Mobility AI", "Industrial IoT"],
                "market_density": "Medium"
            },
            "Arizona": {
                "cities": ["Phoenix", "Scottsdale", "Tempe", "Mesa"],
                "tech_hub_tags": ["Semiconductors", "RealEstateTech", "Health Services"],
                "market_density": "Medium"
            }
        }
    },
    "United Kingdom": {
        "code": "GB",
        "region": "Europe",
        "purchasing_power_tier": "Tier-1",
        "currency": "GBP",
        "states_provinces": {
            "Greater London": {
                "cities": ["London", "Westminster", "Canary Wharf", "Shoreditch", "Camden"],
                "tech_hub_tags": ["FinTech", "AI Labs", "LegalTech", "AdTech", "HealthTech"],
                "market_density": "Ultra-High"
            },
            "Cambridgeshire": {
                "cities": ["Cambridge", "Peterborough", "Ely"],
                "tech_hub_tags": ["DeepTech (Silicon Fen)", "BioTech", "Semiconductor IP", "AI"],
                "market_density": "Very-High"
            },
            "Oxfordshire": {
                "cities": ["Oxford", "Banbury", "Didcot"],
                "tech_hub_tags": ["Quantum Computing", "BioTech", "SpaceTech"],
                "market_density": "Very-High"
            },
            "Greater Manchester": {
                "cities": ["Manchester", "Salford", "MediaCityUK", "Bolton"],
                "tech_hub_tags": ["eCommerce", "MediaTech", "FinTech", "Cybersecurity"],
                "market_density": "High"
            },
            "West Midlands": {
                "cities": ["Birmingham", "Coventry", "Wolverhampton"],
                "tech_hub_tags": ["CleanMobility", "GovTech", "HealthTech"],
                "market_density": "Medium-High"
            },
            "Scotland": {
                "cities": ["Edinburgh", "Glasgow", "Aberdeen", "Dundee"],
                "tech_hub_tags": ["InsurTech", "Gaming Tech", "Space Satellites", "EnergyTech"],
                "market_density": "High"
            },
            "South West England": {
                "cities": ["Bristol", "Bath", "Exeter", "Cheltenham"],
                "tech_hub_tags": ["Aerospace", "Cybersecurity (GCHQ Cluster)", "MicroElectronics"],
                "market_density": "High"
            }
        }
    },
    "Canada": {
        "code": "CA",
        "region": "North America",
        "purchasing_power_tier": "Tier-1",
        "currency": "CAD",
        "states_provinces": {
            "Ontario": {
                "cities": ["Toronto", "Waterloo", "Ottawa", "Mississauga", "Markham"],
                "tech_hub_tags": ["AI (Vector Institute)", "FinTech", "Telecom", "Enterprise SaaS"],
                "market_density": "Ultra-High"
            },
            "British Columbia": {
                "cities": ["Vancouver", "Victoria", "Burnaby", "Richmond", "Kelowna"],
                "tech_hub_tags": ["Gaming", "Visual FX", "CleanTech", "Quantum Tech"],
                "market_density": "Very-High"
            },
            "Quebec": {
                "cities": ["Montreal", "Quebec City", "Laval"],
                "tech_hub_tags": ["Deep Learning (Mila)", "Video Games", "Aerospace"],
                "market_density": "Very-High"
            },
            "Alberta": {
                "cities": ["Calgary", "Edmonton"],
                "tech_hub_tags": ["Energy Transition Tech", "AgriTech", "Reinforcement Learning (Amii)"],
                "market_density": "High"
            }
        }
    },
    "Germany": {
        "code": "DE",
        "region": "Europe",
        "purchasing_power_tier": "Tier-1",
        "currency": "EUR",
        "states_provinces": {
            "Berlin": {
                "cities": ["Berlin", "Potsdam"],
                "tech_hub_tags": ["B2C Apps", "FinTech", "ClimateTech", "AI Startups"],
                "market_density": "Ultra-High"
            },
            "Bavaria": {
                "cities": ["Munich", "Nuremberg", "Augsburg", "Ingolstadt"],
                "tech_hub_tags": ["Enterprise B2B (Siemens/BMW)", "Industrial IoT", "DeepTech"],
                "market_density": "Ultra-High"
            },
            "Hesse": {
                "cities": ["Frankfurt", "Wiesbaden", "Darmstadt"],
                "tech_hub_tags": ["Banking/FinTech (ECB)", "Cybersecurity", "Data Centers"],
                "market_density": "Very-High"
            },
            "Baden-Württemberg": {
                "cities": ["Stuttgart", "Karlsruhe", "Heidelberg", "Mannheim"],
                "tech_hub_tags": ["Automotive Software", "Industry 4.0", "LifeSciences"],
                "market_density": "Very-High"
            },
            "North Rhine-Westphalia": {
                "cities": ["Cologne", "Dusseldorf", "Dortmund", "Essen"],
                "tech_hub_tags": ["InsurTech", "eCommerce", "Digital Retail", "Logistics"],
                "market_density": "High"
            },
            "Hamburg": {
                "cities": ["Hamburg"],
                "tech_hub_tags": ["Maritime Logistics", "MediaTech", "Gaming"],
                "market_density": "High"
            }
        }
    },
    "France": {
        "code": "FR",
        "region": "Europe",
        "purchasing_power_tier": "Tier-1",
        "currency": "EUR",
        "states_provinces": {
            "Île-de-France": {
                "cities": ["Paris", "Boulogne-Billancourt", "Station F", "La Défense"],
                "tech_hub_tags": ["Generative AI (Mistral)", "Luxury eCommerce", "FinTech"],
                "market_density": "Ultra-High"
            },
            "Auvergne-Rhône-Alpes": {
                "cities": ["Lyon", "Grenoble"],
                "tech_hub_tags": ["Semiconductors (Silicon Grenoble)", "BioTech", "Cleantech"],
                "market_density": "High"
            },
            "Provence-Alpes-Côte d'Azur": {
                "cities": ["Nice", "Marseille", "Sophia Antipolis"],
                "tech_hub_tags": ["Telecom", "AI/IoT", "Cloud"],
                "market_density": "High"
            },
            "Occitanie": {
                "cities": ["Toulouse", "Montpellier"],
                "tech_hub_tags": ["Aerospace & Defense (Airbus)", "HealthTech"],
                "market_density": "High"
            }
        }
    },
    "Australia": {
        "code": "AU",
        "region": "Asia-Pacific",
        "purchasing_power_tier": "Tier-1",
        "currency": "AUD",
        "states_provinces": {
            "New South Wales": {
                "cities": ["Sydney", "Newcastle", "Wollongong"],
                "tech_hub_tags": ["FinTech", "B2B SaaS (Atlassian/Canva)", "PropTech"],
                "market_density": "Ultra-High"
            },
            "Victoria": {
                "cities": ["Melbourne", "Geelong", "Ballarat"],
                "tech_hub_tags": ["MedTech", "EdTech", "Design Software", "eCommerce"],
                "market_density": "Very-High"
            },
            "Queensland": {
                "cities": ["Brisbane", "Gold Coast", "Sunshine Coast"],
                "tech_hub_tags": ["BioTech", "AgTech", "TourismTech"],
                "market_density": "High"
            },
            "Western Australia": {
                "cities": ["Perth", "Fremantle"],
                "tech_hub_tags": ["Mining Tech", "Clean Energy", "Automation Robotics"],
                "market_density": "High"
            }
        }
    },
    "Netherlands": {
        "code": "NL",
        "region": "Europe",
        "purchasing_power_tier": "Tier-1",
        "currency": "EUR",
        "states_provinces": {
            "North Holland": {
                "cities": ["Amsterdam", "Haarlem", "Hilversum"],
                "tech_hub_tags": ["Adyen FinTech", "AdTech", "High-Speed Interconnects", "AI"],
                "market_density": "Ultra-High"
            },
            "North Brabant": {
                "cities": ["Eindhoven (Brainport)", "Tilburg", "Breda"],
                "tech_hub_tags": ["Semiconductors (ASML)", "High-Tech Hardware", "Photonics"],
                "market_density": "Very-High"
            },
            "South Holland": {
                "cities": ["Rotterdam", "The Hague", "Delft"],
                "tech_hub_tags": ["Quantum Delft", "Port Logistics Tech", "Cybersecurity"],
                "market_density": "Very-High"
            },
            "Utrecht": {
                "cities": ["Utrecht", "Amersfoort"],
                "tech_hub_tags": ["Gaming", "HealthTech", "Sustainability"],
                "market_density": "High"
            }
        }
    },
    "Switzerland": {
        "code": "CH",
        "region": "Europe",
        "purchasing_power_tier": "Tier-1 (High-Ticket)",
        "currency": "CHF",
        "states_provinces": {
            "Zurich": {
                "cities": ["Zurich", "Winterthur"],
                "tech_hub_tags": ["Google Zurich Engineering", "FinTech Banking", "Crypto/Web3", "Robotics"],
                "market_density": "Ultra-High"
            },
            "Vaud": {
                "cities": ["Lausanne (EPFL)", "Montreux", "Vevey"],
                "tech_hub_tags": ["HealthTech", "Precision Ag", "AI Research"],
                "market_density": "Very-High"
            },
            "Geneva": {
                "cities": ["Geneva"],
                "tech_hub_tags": ["Private Banking Tech", "Commodities Tech", "Gov/UN Tech"],
                "market_density": "High"
            },
            "Zug": {
                "cities": ["Zug (Crypto Valley)", "Baar"],
                "tech_hub_tags": ["Blockchain Protocol", "Decentralized Finance", "FinTech"],
                "market_density": "Very-High"
            }
        }
    },
    "United Arab Emirates": {
        "code": "AE",
        "region": "Middle East",
        "purchasing_power_tier": "Tier-1 (High-Ticket)",
        "currency": "AED",
        "states_provinces": {
            "Dubai": {
                "cities": ["Dubai (DIFC, Internet City, Business Bay)", "Jebel Ali", "Silicon Oasis"],
                "tech_hub_tags": ["AI Governance", "FinTech", "PropTech", "Logistics", "Web3"],
                "market_density": "Ultra-High"
            },
            "Abu Dhabi": {
                "cities": ["Abu Dhabi (Hub71, ADGM)", "Al Ain"],
                "tech_hub_tags": ["Sovereign AI (TII Falcon)", "Clean Energy", "DefenseTech"],
                "market_density": "Very-High"
            }
        }
    },
    "Singapore": {
        "code": "SG",
        "region": "Asia-Pacific",
        "purchasing_power_tier": "Tier-1",
        "currency": "SGD",
        "states_provinces": {
            "Singapore": {
                "cities": ["Singapore (CBD)", "One-North", "Jurong Innovation District", "Marina Bay"],
                "tech_hub_tags": ["APAC FinTech HQ", "Logistics Tech", "DeepTech", "Biomedical"],
                "market_density": "Ultra-High"
            }
        }
    },
    "Japan": {
        "code": "JP",
        "region": "Asia-Pacific",
        "purchasing_power_tier": "Tier-1",
        "currency": "JPY",
        "states_provinces": {
            "Tokyo Prefecture": {
                "cities": ["Tokyo (Shibuya, Roppongi, Marunouchi, Shinagawa)", "Hachioji"],
                "tech_hub_tags": ["Robotics", "Enterprise Modernization", "Gaming", "FinTech"],
                "market_density": "Ultra-High"
            },
            "Osaka Prefecture": {
                "cities": ["Osaka", "Sakai"],
                "tech_hub_tags": ["Electronics", "Pharma", "Industrial Automation"],
                "market_density": "High"
            },
            "Kyoto Prefecture": {
                "cities": ["Kyoto"],
                "tech_hub_tags": ["Semiconductors", "Gaming (Nintendo)", "Nanotech"],
                "market_density": "High"
            },
            "Kanagawa Prefecture": {
                "cities": ["Yokohama", "Kawasaki"],
                "tech_hub_tags": ["Mobility", "Telecom", "AI Hardware"],
                "market_density": "High"
            }
        }
    },
    "Ireland": {
        "code": "IE",
        "region": "Europe",
        "purchasing_power_tier": "Tier-1",
        "currency": "EUR",
        "states_provinces": {
            "Leinster": {
                "cities": ["Dublin (Silicon Docks)", "Dun Laoghaire", "Dundalk"],
                "tech_hub_tags": ["European Tech HQs", "Data Infrastructure", "FinTech", "SaaS"],
                "market_density": "Ultra-High"
            },
            "Munster": {
                "cities": ["Cork", "Limerick", "Waterford"],
                "tech_hub_tags": ["Apple European Operations", "BioPharma", "Cybersecurity"],
                "market_density": "High"
            },
            "Connacht": {
                "cities": ["Galway"],
                "tech_hub_tags": ["MedTech Global Cluster", "Marine Tech"],
                "market_density": "High"
            }
        }
    },
    "Sweden": {
        "code": "SE",
        "region": "Europe",
        "purchasing_power_tier": "Tier-1",
        "currency": "SEK",
        "states_provinces": {
            "Stockholm County": {
                "cities": ["Stockholm (Kista)", "Solna", "Sodertalje"],
                "tech_hub_tags": ["Unicorn Factory (Spotify/Klarna)", "Gaming", "CleanTech"],
                "market_density": "Ultra-High"
            },
            "Västra Götaland": {
                "cities": ["Gothenburg", "Boras"],
                "tech_hub_tags": ["Automotive Tech (Volvo)", "Telematics", "MedTech"],
                "market_density": "High"
            },
            "Skåne": {
                "cities": ["Malmö", "Lund (Ideon Science Park)"],
                "tech_hub_tags": ["Mobile Comms", "Life Sciences", "Cross-Border MedTech"],
                "market_density": "High"
            }
        }
    },
    "India": {
        "code": "IN",
        "region": "Asia-Pacific",
        "purchasing_power_tier": "Tier-2 (High-Growth Hub)",
        "currency": "INR",
        "states_provinces": {
            "Karnataka": {
                "cities": ["Bengaluru (Whitefield, Koramangala, Indiranagar, Electronic City)", "Mysuru"],
                "tech_hub_tags": ["Silicon Valley of India", "AI/ML Startups", "Global Capability Centers (GCCs)", "SaaS"],
                "market_density": "Ultra-High"
            },
            "Maharashtra": {
                "cities": ["Mumbai (BKC, Powai, Andheri)", "Pune (Hinjawadi, Magarpatta)"],
                "tech_hub_tags": ["FinTech Capital", "AutoTech", "Enterprise Software", "MediaTech"],
                "market_density": "Ultra-High"
            },
            "Telangana": {
                "cities": ["Hyderabad (HITEC City, Gachibowli)"],
                "tech_hub_tags": ["PharmaTech", "Cloud Hyperscalers", "Defense & Aerospace", "AI Hub"],
                "market_density": "Very-High"
            },
            "Delhi NCR": {
                "cities": ["Gurugram (Cyber City)", "Noida", "New Delhi"],
                "tech_hub_tags": ["B2C Unicorns", "eCommerce Logistics", "EdTech", "FinTech"],
                "market_density": "Very-High"
            },
            "Tamil Nadu": {
                "cities": ["Chennai (OMR)", "Coimbatore"],
                "tech_hub_tags": ["SaaS Capital (Freshworks/Zoho)", "Automotive Software", "Hardware"],
                "market_density": "High"
            }
        }
    },
    "Saudi Arabia": {
        "code": "SA",
        "region": "Middle East",
        "purchasing_power_tier": "Tier-1 (High-Ticket)",
        "currency": "SAR",
        "states_provinces": {
            "Riyadh Province": {
                "cities": ["Riyadh (KAFD, Digital City, Olaya)", "Al Kharj"],
                "tech_hub_tags": ["Vision 2030 Megaprojects", "GovTech", "FinTech", "Enterprise Cloud Migration"],
                "market_density": "Ultra-High"
            },
            "Makkah Province": {
                "cities": ["Jeddah", "Mecca"],
                "tech_hub_tags": ["Logistics & Port Tech", "Hospitality AI", "Smart City"],
                "market_density": "High"
            },
            "Eastern Province": {
                "cities": ["Dammam", "Khobar", "Dhahran"],
                "tech_hub_tags": ["Aramco Industrial Tech", "Energy Transition", "Cybersecurity"],
                "market_density": "High"
            }
        }
    }
}

class GeoDatabase:
    @staticmethod
    def get_all_countries() -> List[str]:
        """Returns sorted list of all available countries."""
        return sorted(list(GLOBAL_GEO_REGISTRY.keys()))

    @staticmethod
    def get_country_info(country: str) -> Optional[Dict[str, Any]]:
        return GLOBAL_GEO_REGISTRY.get(country)

    @staticmethod
    def get_states_provinces(country: str) -> List[str]:
        info = GLOBAL_GEO_REGISTRY.get(country)
        if not info:
            return []
        return sorted(list(info.get("states_provinces", {}).keys()))

    @staticmethod
    def get_cities(country: str, state_province: str) -> List[str]:
        info = GLOBAL_GEO_REGISTRY.get(country)
        if not info:
            return []
        states = info.get("states_provinces", {})
        state_data = states.get(state_province)
        if not state_data:
            return []
        return state_data.get("cities", [])

    @staticmethod
    def get_tech_tags(country: str, state_province: str) -> List[str]:
        info = GLOBAL_GEO_REGISTRY.get(country)
        if not info:
            return []
        state_data = info.get("states_provinces", {}).get(state_province, {})
        return state_data.get("tech_hub_tags", [])

    @staticmethod
    def search_cities_globally(query: str) -> List[Dict[str, str]]:
        """Searches across all countries, states, and cities for matching locations."""
        query_lower = query.lower().strip()
        matches = []
        for country, c_data in GLOBAL_GEO_REGISTRY.items():
            for state, s_data in c_data.get("states_provinces", {}).items():
                for city in s_data.get("cities", []):
                    if query_lower in city.lower() or query_lower in state.lower() or query_lower in country.lower():
                        matches.append({
                            "city": city,
                            "state_province": state,
                            "country": country,
                            "region": c_data.get("region", "Global"),
                            "purchasing_power": c_data.get("purchasing_power_tier", "Tier-1")
                        })
        return matches[:25]
