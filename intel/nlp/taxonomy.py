"""Vocabulary the search understands: kinds of local business, professional skills, and places. Each entry: canonical name -> synonyms."""

BUSINESS = {
    # health
    "dentist": ["dental", "dentistry", "dental clinic", "orthodontist", "teeth"], "doctor": ["gp", "physician", "medical practice", "family doctor", "clinic doctor"],
    "clinic": ["medical clinic", "health clinic", "walk in clinic", "urgent care"], "pharmacy": ["chemist", "drugstore"], "veterinary": ["vet", "veterinarian", "animal hospital", "pet clinic"],
    "physiotherapist": ["physio", "physical therapy", "physiotherapy"], "chiropractor": ["chiropractic"], "optician": ["optometrist", "eye clinic", "eyewear"], "dermatologist": ["skin clinic"],
    "psychologist": ["therapist", "counsellor", "counselor", "mental health"], "hospital": ["medical center", "medical centre"], "care home": ["nursing home", "elderly care", "assisted living"],
    "gym": ["fitness center", "fitness centre", "health club", "crossfit"], "yoga studio": ["yoga", "pilates studio", "pilates"], "spa": ["day spa", "wellness center", "massage"],
    # beauty / personal
    "salon": ["hair salon", "hairdresser", "barber", "barbershop", "hair stylist"], "beauty salon": ["beauty parlour", "nail salon", "nails", "beautician", "cosmetics"], "tattoo studio": ["tattoo"],
    # food / hospitality
    "restaurant": ["eatery", "bistro", "diner", "takeaway", "takeout", "pizzeria"], "cafe": ["coffee shop", "coffee", "tea room"], "bar": ["pub", "tavern", "nightclub"], "bakery": ["patisserie", "bread shop"],
    "hotel": ["motel", "guest house", "bed and breakfast", "bnb", "hostel", "resort"], "catering": ["caterer", "event catering"], "food truck": ["street food"],
    # professional services
    "lawyer": ["attorney", "solicitor", "law firm", "legal services", "barrister"], "accountant": ["accounting firm", "bookkeeper", "tax advisor", "cpa", "auditor"],
    "real estate": ["estate agent", "realtor", "property agent", "letting agent", "property management"], "insurance": ["insurance broker", "insurance agency"], "financial advisor": ["wealth manager", "mortgage broker", "financial planner"],
    "architect": ["architecture firm", "architectural"], "engineering firm": ["civil engineer", "structural engineer", "consulting engineers"], "consultant": ["consultancy", "management consulting", "business consultant"],
    "marketing agency": ["advertising agency", "digital agency", "pr agency", "seo agency", "branding agency"], "recruitment agency": ["recruiter", "staffing agency", "employment agency", "headhunter"],
    "notary": ["notary public"], "translator": ["translation services"], "photographer": ["photography studio", "wedding photographer"], "printing": ["print shop", "printer"],
    # trades / home
    "plumber": ["plumbing", "plumbing services"], "electrician": ["electrical services", "electrical contractor"], "builder": ["construction", "building contractor", "general contractor", "construction company"],
    "roofer": ["roofing", "roofing contractor"], "carpenter": ["joiner", "carpentry"], "painter": ["decorator", "painting contractor", "painter and decorator"], "locksmith": ["lock repair"],
    "hvac": ["heating", "air conditioning", "boiler installer", "heating engineer"], "cleaning service": ["cleaner", "maid service", "janitorial", "commercial cleaning"], "landscaper": ["gardener", "landscaping", "lawn care", "tree surgeon"],
    "pest control": ["exterminator"], "removals": ["moving company", "movers", "relocation"], "interior designer": ["interior design"], "solar installer": ["solar panels", "renewable energy"],
    "pool service": ["swimming pool"], "garage door": ["garage doors"], "window installer": ["windows and doors", "glazing"], "flooring": ["carpet", "floor installer"], "handyman": ["odd jobs"],
    # retail
    "florist": ["flower shop", "flowers"], "clothing store": ["boutique", "fashion store", "apparel"], "furniture store": ["furniture"], "electronics store": ["computer shop", "phone shop"],
    "jewelry store": ["jeweller", "jeweler", "jewellery"], "bookstore": ["book shop"], "supermarket": ["grocery", "grocery store", "convenience store", "mini market"], "pet shop": ["pet store", "pet supplies"],
    "toy store": ["toy shop"], "hardware store": ["diy store", "building supplies"], "gift shop": ["souvenir shop"], "bicycle shop": ["bike shop", "cycle shop"], "sports shop": ["sporting goods"],
    # auto
    "car repair": ["garage", "mechanic", "auto repair", "auto shop", "car service", "tyre shop", "mot"], "car dealer": ["car dealership", "used cars", "auto dealer", "car sales"], "car wash": ["car valeting", "detailing"],
    "driving school": ["driving instructor", "driving lessons"], "taxi": ["cab", "minicab", "chauffeur"], "motorcycle shop": ["motorbike", "motorcycle dealer"],
    # education / community
    "school": ["primary school", "high school", "academy", "private school", "kindergarten", "nursery"], "tutor": ["tutoring", "tuition", "learning center", "language school"], "university": ["college"],
    "daycare": ["childcare", "child care", "preschool"], "church": ["place of worship", "mosque", "temple", "synagogue"], "nonprofit": ["charity", "ngo", "foundation"], "dance studio": ["dance school", "music school"],
    # other
    "travel agency": ["tour operator", "travel agent", "holiday company"], "event venue": ["wedding venue", "function room", "event planner", "wedding planner"], "storage": ["self storage"], "funeral home": ["funeral director"],
    "logistics": ["freight", "courier", "delivery service", "shipping company", "trucking"], "manufacturer": ["factory", "manufacturing", "fabrication", "workshop"], "farm": ["farm shop", "agriculture", "nursery garden"],
    "software company": ["software house", "it company", "tech company", "it services", "software agency", "app developer"], "web design agency": ["web designer", "website design"], "coworking space": ["co-working", "shared office"],
    "security company": ["security guards", "alarm installer", "cctv installer"], "laundry": ["dry cleaner", "laundrette", "laundromat"], "tailor": ["alterations", "seamstress"], "repair shop": ["phone repair", "computer repair", "it repair"],
}

SKILLS = {
    # languages
    "python": ["py", "python3", "django", "flask", "fastapi"], "javascript": ["js", "ecmascript", "node", "nodejs", "node.js"], "typescript": ["ts"], "java": ["spring boot", "jvm", "spring"], "c#": ["csharp", "dotnet", ".net", "asp.net"],
    "php": ["laravel", "symfony", "codeigniter"], "ruby": ["rails", "ruby on rails", "ror"], "go": ["golang"], "rust": ["rustlang"], "swift": ["ios development", "swiftui"], "kotlin": ["android development"],
    "c++": ["cpp"], "scala": ["akka"], "sql": ["postgres", "postgresql", "mysql", "database", "databases"], "r": ["r language", "rstats"],
    # web / frontend / backend
    "react": ["reactjs", "react.js", "next.js", "nextjs", "react native"], "vue": ["vuejs", "vue.js", "nuxt"], "angular": ["angularjs"], "svelte": ["sveltekit"], "html css": ["html", "css", "frontend", "front end", "front-end"],
    "backend": ["back end", "back-end", "api development", "rest api", "graphql", "microservices"], "full stack": ["fullstack", "full-stack", "web development", "web developer", "web app", "web application"],
    "wordpress": ["wp", "woocommerce", "elementor"], "shopify": ["shopify plus", "liquid"], "ecommerce": ["e-commerce", "online store", "online shop", "magento", "bigcommerce"], "webflow": ["no code website"],
    # mobile
    "mobile app": ["mobile development", "ios", "android", "flutter", "react native", "app development"],
    # cloud / devops / security
    "aws": ["amazon web services", "ec2", "lambda", "s3"], "azure": ["microsoft azure"], "gcp": ["google cloud", "google cloud platform"], "devops": ["ci/cd", "cicd", "site reliability", "sre", "infrastructure"],
    "kubernetes": ["k8s", "helm"], "docker": ["containers", "containerization"], "terraform": ["infrastructure as code", "iac"], "cloud migration": ["cloud modernization", "legacy modernization", "legacy migration"],
    "cybersecurity": ["security", "infosec", "penetration testing", "pentest", "application security", "appsec", "security audit", "soc2", "iso 27001"], "linux": ["sysadmin", "system administration"],
    # data / ai
    "machine learning": ["ml", "deep learning", "neural networks", "data science", "ai engineer"], "ai": ["artificial intelligence", "llm", "large language model", "generative ai", "genai", "chatbot", "chatgpt", "openai", "rag", "ai agents"],
    "computer vision": ["image recognition", "opencv", "object detection", "ocr"], "nlp": ["natural language processing", "text mining", "language model"], "data engineering": ["etl", "data pipeline", "airflow", "spark", "data warehouse", "bigquery", "snowflake"],
    "data analysis": ["analytics", "business intelligence", "bi", "tableau", "power bi", "dashboards"], "blockchain": ["web3", "smart contracts", "solidity", "crypto", "ethereum"], "iot": ["internet of things", "embedded", "firmware", "arduino"],
    "robotics": ["ros", "automation engineering"], "game development": ["unity", "unreal", "game dev", "gamedev"], "ar vr": ["augmented reality", "virtual reality", "xr"],
    "automation": ["rpa", "workflow automation", "zapier", "make.com", "n8n", "scraping", "web scraping", "bots"], "crm": ["salesforce", "hubspot", "zoho", "dynamics 365"], "erp": ["sap", "odoo", "netsuite"],
    # design / content / marketing
    "ui ux design": ["ux", "ui", "user experience", "figma", "product design", "web design", "graphic design", "design system"], "branding": ["logo design", "brand identity"], "video editing": ["video production", "motion graphics", "animation", "after effects"],
    "seo": ["search engine optimization", "search engine optimisation", "technical seo", "local seo"], "content writing": ["copywriting", "technical writing", "blog writing", "content marketing"], "digital marketing": ["ppc", "google ads", "facebook ads", "social media marketing", "email marketing", "growth marketing"],
    "social media": ["community management", "influencer"], "translation": ["localization", "localisation", "transcription"],
    # management / qa / other
    "project management": ["scrum master", "agile", "product manager", "product management", "delivery manager", "pm"], "qa testing": ["quality assurance", "test automation", "selenium", "cypress", "playwright", "manual testing"],
    "technical support": ["it support", "helpdesk", "help desk", "customer support"], "accessibility": ["wcag", "a11y", "ada compliance"], "performance optimization": ["core web vitals", "page speed", "website speed", "web performance"],
    "api integration": ["integrations", "webhooks", "payment integration", "stripe integration"], "legal ops": ["compliance", "gdpr", "privacy"], "finance": ["accounting software", "fintech", "bookkeeping"],
}

QUALIFIERS = {
    "remote": ["work from home", "wfh", "anywhere", "distributed", "telecommute"], "freelance": ["freelancer", "contract", "contractor", "gig", "part time project", "one off"],
    "full time": ["permanent", "full-time"], "part time": ["part-time"], "senior": ["lead", "principal", "staff"], "junior": ["entry level", "graduate", "intern"],
}

# kinds of opportunity words
TENDER_WORDS = {"tender", "tenders", "rfp", "rfq", "rfi", "procurement", "government", "public sector", "council", "municipal", "ministry", "federal", "contract notice", "bid", "bids", "public contract"}
JOB_WORDS = {"job", "jobs", "hiring", "hire", "position", "positions", "vacancy", "vacancies", "gig", "gigs", "freelance", "project", "projects", "work", "opening", "openings", "career", "careers", "remote", "contract", "developer", "engineer", "designer", "consultant", "programmer", "specialist", "expert", "architect", "analyst", "writer", "editor", "manager"}
LOCAL_WORDS = {"near", "nearby", "local", "businesses", "business", "companies", "company", "firms", "firm", "places"}
NO_WEBSITE = ["without a website", "without website", "no website", "no web site", "no site", "with no website", "dont have a website", "don't have a website", "doesnt have a website", "doesn't have a website", "missing website", "without site", "no online presence", "no web presence"]
NEEDS_FIX = ["bad website", "slow website", "slow site", "outdated website", "old website", "broken website", "poor website", "ugly website", "not mobile friendly", "no ssl", "no https", "insecure website", "website down", "site down", "slow"]
SOCIAL_ONLY = ["facebook only", "instagram only", "social media only", "only facebook", "only instagram", "just facebook", "just instagram"]

CITIES = [
    "london", "manchester", "birmingham", "leeds", "glasgow", "liverpool", "bristol", "sheffield", "edinburgh", "cardiff", "belfast", "newcastle", "nottingham", "leicester", "southampton", "brighton", "oxford", "cambridge", "york",
    "dublin", "paris", "lyon", "marseille", "berlin", "munich", "hamburg", "frankfurt", "cologne", "amsterdam", "rotterdam", "brussels", "madrid", "barcelona", "valencia", "lisbon", "porto", "rome", "milan", "turin", "naples", "vienna", "zurich", "geneva",
    "stockholm", "oslo", "copenhagen", "helsinki", "warsaw", "krakow", "prague", "budapest", "bucharest", "athens", "istanbul", "ankara", "moscow", "kyiv",
    "new york", "los angeles", "chicago", "houston", "phoenix", "philadelphia", "san antonio", "san diego", "dallas", "austin", "san jose", "san francisco", "seattle", "denver", "boston", "miami", "atlanta", "las vegas", "portland", "washington", "detroit", "minneapolis", "orlando", "tampa", "charlotte", "nashville", "salt lake city",
    "toronto", "vancouver", "montreal", "calgary", "ottawa", "mexico city", "bogota", "lima", "santiago", "buenos aires", "sao paulo", "rio de janeiro",
    "dubai", "abu dhabi", "doha", "riyadh", "jeddah", "kuwait city", "muscat", "manama", "cairo", "lagos", "nairobi", "johannesburg", "cape town", "casablanca", "accra", "addis ababa",
    "karachi", "lahore", "islamabad", "rawalpindi", "faisalabad", "peshawar", "delhi", "mumbai", "bangalore", "bengaluru", "hyderabad", "chennai", "kolkata", "pune", "ahmedabad", "dhaka", "colombo", "kathmandu",
    "singapore", "kuala lumpur", "jakarta", "bangkok", "manila", "hanoi", "ho chi minh city", "hong kong", "shanghai", "beijing", "shenzhen", "tokyo", "osaka", "seoul", "taipei", "sydney", "melbourne", "brisbane", "perth", "auckland", "wellington",
]
