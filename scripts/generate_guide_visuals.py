import os

dirs = [
    'frontend/public/images',
    '/Users/irfan/.gemini/antigravity/brain/741fcf11-c8cd-4a75-9717-60c91080be02/images'
]
for d in dirs:
    os.makedirs(d, exist_ok=True)

# 1. Pipeline Architecture SVG
svg1 = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1200 480" width="1200" height="480">
  <defs>
    <linearGradient id="bg" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#080b12"/>
      <stop offset="50%" stop-color="#0f172a"/>
      <stop offset="100%" stop-color="#05070b"/>
    </linearGradient>
    <linearGradient id="card" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#1e293b" stop-opacity="0.9"/>
      <stop offset="100%" stop-color="#0f172a" stop-opacity="0.95"/>
    </linearGradient>
  </defs>

  <rect width="1200" height="480" rx="24" fill="url(#bg)" stroke="#1e293b" stroke-width="2"/>

  <!-- Title Badge -->
  <rect x="40" y="32" width="280" height="32" rx="16" fill="#6366f1" fill-opacity="0.15" stroke="#6366f1" stroke-opacity="0.4"/>
  <circle cx="56" cy="48" r="5" fill="#10b981"/>
  <text x="72" y="53" fill="#c7d2fe" font-family="ui-monospace, monospace" font-size="12" font-weight="bold">END-TO-END AUTONOMOUS LOOP</text>

  <!-- Main Headline -->
  <text x="40" y="100" fill="#ffffff" font-family="system-ui, -apple-system, sans-serif" font-size="24" font-weight="800">Sovereign Multi-Agent Pipeline Architecture</text>
  <text x="40" y="126" fill="#94a3b8" font-family="system-ui, -apple-system, sans-serif" font-size="13">Zero Recurring Cost · $0 API Fees · Automated Discovery, Forensics, Creative, &amp; CRM</text>

  <!-- Connecting Line Behind Cards -->
  <line x1="140" y1="270" x2="1060" y2="270" stroke="#334155" stroke-width="4" stroke-dasharray="6 6"/>

  <!-- 1. Discovery -->
  <g transform="translate(40, 160)">
    <rect width="205" height="240" rx="18" fill="url(#card)" stroke="#6366f1" stroke-width="2"/>
    <circle cx="36" cy="36" r="16" fill="#6366f1" fill-opacity="0.2" stroke="#6366f1"/>
    <text x="32" y="41" fill="#818cf8" font-family="monospace" font-size="14" font-weight="bold">1</text>
    <text x="64" y="41" fill="#ffffff" font-family="system-ui, sans-serif" font-size="15" font-weight="bold">Discovery</text>
    <rect x=\"18\" y=\"68\" width=\"169\" height=\"2\" fill=\"#334155\"/>
    <text x="20" y="94" fill="#cbd5e1" font-family="system-ui, sans-serif" font-size="12" font-weight="bold">Sourcing Scout</text>
    <text x="20" y="116" fill="#94a3b8" font-family="system-ui, sans-serif" font-size="11">• SEC EDGAR Form D</text>
    <text x="20" y="136" fill="#94a3b8" font-family="system-ui, sans-serif" font-size="11">• OpenStreetMap Geo</text>
    <text x="20" y="156" fill="#94a3b8" font-family="system-ui, sans-serif" font-size="11">• Upwork &amp; Tender Radar</text>
    <text x="20" y="176" fill="#94a3b8" font-family="system-ui, sans-serif" font-size="11">• GitHub Bounties</text>
    <rect x="20" y="198" width="120" height="22" rx="6" fill="#6366f1" fill-opacity="0.2" stroke="#6366f1" stroke-opacity="0.5"/>
    <text x="28" y="213" fill="#a5b4fc" font-family="monospace" font-size="10" font-weight="bold">Live Ingestion</text>
  </g>

  <!-- 2. Forensics -->
  <g transform="translate(270, 160)">
    <rect width="205" height="240" rx="18" fill="url(#card)" stroke="#10b981" stroke-width="2"/>
    <circle cx="36" cy="36" r="16" fill="#10b981" fill-opacity="0.2" stroke="#10b981"/>
    <text x="32" y="41" fill="#34d399" font-family="monospace" font-size="14" font-weight="bold">2</text>
    <text x="64" y="41" fill="#ffffff" font-family="system-ui, sans-serif" font-size="15" font-weight="bold">Audit Forensics</text>
    <rect x=\"18\" y=\"68\" width=\"169\" height=\"2\" fill=\"#334155\"/>
    <text x="20" y="94" fill="#cbd5e1" font-family="system-ui, sans-serif" font-size="12" font-weight="bold">Website Doctor</text>
    <text x="20" y="116" fill="#94a3b8" font-family="system-ui, sans-serif" font-size="11">• Core Web Vitals (LCP)</text>
    <text x="20" y="136" fill="#94a3b8" font-family="system-ui, sans-serif" font-size="11">• TTFB Server Speed</text>
    <text x="20" y="156" fill="#94a3b8" font-family="system-ui, sans-serif" font-size="11">• SSL &amp; Security Headers</text>
    <text x="20" y="176" fill="#94a3b8" font-family="system-ui, sans-serif" font-size="11">• Stack Fingerprinting</text>
    <rect x="20" y="198" width="110" height="22" rx="6" fill="#10b981" fill-opacity="0.2" stroke="#10b981" stroke-opacity="0.5"/>
    <text x="28" y="213" fill="#6ee7b7" font-family="monospace" font-size="10" font-weight="bold">Speed &amp; SEO</text>
  </g>

  <!-- 3. Pitch Studio -->
  <g transform="translate(500, 160)">
    <rect width="205" height="240" rx="18" fill="url(#card)" stroke="#a855f7" stroke-width="2"/>
    <circle cx="36" cy="36" r="16" fill="#a855f7" fill-opacity="0.2" stroke="#a855f7"/>
    <text x="32" y="41" fill="#c084fc" font-family="monospace" font-size="14" font-weight="bold">3</text>
    <text x="64" y="41" fill="#ffffff" font-family="system-ui, sans-serif" font-size="15" font-weight="bold">Creative Pitch</text>
    <rect x=\"18\" y=\"68\" width=\"169\" height=\"2\" fill=\"#334155\"/>
    <text x="20" y="94" fill="#cbd5e1" font-family="system-ui, sans-serif" font-size="12" font-weight="bold">Video &amp; Copy</text>
    <text x="20" y="116" fill="#94a3b8" font-family="system-ui, sans-serif" font-size="11">• 4-Scene Loom Script</text>
    <text x="20" y="136" fill="#94a3b8" font-family="system-ui, sans-serif" font-size="11">• Lavender 90+ Copy</text>
    <text x="20" y="156" fill="#94a3b8" font-family="system-ui, sans-serif" font-size="11">• Zero-Spam Triggering</text>
    <text x="20" y="176" fill="#94a3b8" font-family="system-ui, sans-serif" font-size="11">• Verifiable SOW Bids</text>
    <rect x="20" y="198" width="115" height="22" rx="6" fill="#a855f7" fill-opacity="0.2" stroke="#a855f7" stroke-opacity="0.5"/>
    <text x="28" y="213" fill="#d8b4fe" font-family="monospace" font-size="10" font-weight="bold">60s Storyboard</text>
  </g>

  <!-- 4. Deliverability -->
  <g transform="translate(730, 160)">
    <rect width="205" height="240" rx="18" fill="url(#card)" stroke="#06b6d4" stroke-width="2"/>
    <circle cx="36" cy="36" r="16" fill="#06b6d4" fill-opacity="0.2" stroke="#06b6d4"/>
    <text x="32" y="41" fill="#22d3ee" font-family="monospace" font-size="14" font-weight="bold">4</text>
    <text x="64" y="41" fill="#ffffff" font-family="system-ui, sans-serif" font-size="15" font-weight="bold">Deliverability</text>
    <rect x=\"18\" y=\"68\" width=\"169\" height=\"2\" fill=\"#334155\"/>
    <text x="20" y="94" fill="#cbd5e1" font-family="system-ui, sans-serif" font-size="12" font-weight="bold">Fleet Sentinel</text>
    <text x="20" y="116" fill="#94a3b8" font-family="system-ui, sans-serif" font-size="11">• Mailbox ESP Rotation</text>
    <text x="20" y="136" fill="#94a3b8" font-family="system-ui, sans-serif" font-size="11">• Spintax Permutations</text>
    <text x="20" y="156" fill="#94a3b8" font-family="system-ui, sans-serif" font-size="11">• CAN-SPAM HMAC Vault</text>
    <text x="20" y="176" fill="#94a3b8" font-family="system-ui, sans-serif" font-size="11">• Auto-Stop on Reply</text>
    <rect x="20" y="198" width="125" height="22" rx="6" fill="#06b6d4" fill-opacity="0.2" stroke="#06b6d4" stroke-opacity="0.5"/>
    <text x="28" y="213" fill="#67e8f9" font-family="monospace" font-size="10" font-weight="bold">Inbox Protected</text>
  </g>

  <!-- 5. Revenue CRM -->
  <g transform="translate(960, 160)">
    <rect width="200" height="240" rx="18" fill="url(#card)" stroke="#f59e0b" stroke-width="2"/>
    <circle cx="36" cy="36" r="16" fill="#f59e0b" fill-opacity="0.2" stroke="#f59e0b"/>
    <text x="32" y="41" fill="#fbbf24" font-family="monospace" font-size="14" font-weight="bold">5</text>
    <text x="64" y="41" fill="#ffffff" font-family="system-ui, sans-serif" font-size="15" font-weight="bold">Revenue CRM</text>
    <rect x=\"18\" y=\"68\" width=\"164\" height=\"2\" fill=\"#334155\"/>
    <text x="20" y="94" fill="#cbd5e1" font-family="system-ui, sans-serif" font-size="12" font-weight="bold">Kanban Pipeline</text>
    <text x="20" y="116" fill="#94a3b8" font-family="system-ui, sans-serif" font-size="11">• 6 Visual Deal Stages</text>
    <text x="20" y="136" fill="#94a3b8" font-family="system-ui, sans-serif" font-size="11">• Weighted Forecasts</text>
    <text x="20" y="156" fill="#94a3b8" font-family="system-ui, sans-serif" font-size="11">• 1-Click Closed Won</text>
    <text x="20" y="176" fill="#94a3b8" font-family="system-ui, sans-serif" font-size="11">• Bayesian Win Loop</text>
    <rect x="20" y="198" width="110" height="22" rx="6" fill="#f59e0b" fill-opacity="0.2" stroke="#f59e0b" stroke-opacity="0.5"/>
    <text x="28" y="213" fill="#fde68a" font-family="monospace" font-size="10" font-weight="bold">Closed Won</text>
  </g>
</svg>"""

# 2. Swarm Simulation SVG
svg2 = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 900 460" width="900" height="460">
  <defs>
    <linearGradient id="terminalBg" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#090d16"/>
      <stop offset="100%" stop-color="#020408"/>
    </linearGradient>
  </defs>
  <rect width="900" height="460" rx="16" fill="url(#terminalBg)" stroke="#1e293b" stroke-width="2"/>
  
  <rect width="900" height="42" rx="16" fill="#0f172a"/>
  <circle cx="24" cy="21" r="6" fill="#ef4444"/>
  <circle cx="42" cy="21" r="6" fill="#f59e0b"/>
  <circle cx="60" cy="21" r="6" fill="#10b981"/>
  <text x="90" y="26" fill="#94a3b8" font-family="monospace" font-size="12">Swarm Autopilot · 4 Agents Active · Native Chromium Daemon</text>

  <g font-family="ui-monospace, SFMono-Regular, Menlo, monospace" font-size="12" transform="translate(24, 70)">
    <text y="20" fill="#38bdf8">[09:44:12] SOURCING SCOUT     ➜ Ingesting SEC EDGAR Form D venture stream...</text>
    <text y="42" fill="#94a3b8">             ✓ Resolved 5 companies with active Series A rounds ($4.2M - $18M).</text>
    <text y="72" fill="#818cf8">[09:44:14] FORENSICS ENGINEER ➜ Crawling target infrastructure: candoriq.com</text>
    <text y="94" fill="#f59e0b">             ⚠ LCP Bottleneck Detected: 4.1s (Unoptimized Hero Banner on 4G)</text>
    <text y="116" fill="#94a3b8">             ✓ Stack: React 18, Next.js 14, Tailwind CSS, AWS CloudFront</text>
    <text y="146" fill="#c084fc">[09:44:16] STRATEGIST POD     ➜ Computing mathematical close probability P(Close)...</text>
    <text y="168" fill="#34d399" font-weight="bold">             ✓ Fit Score: 94% | Expected Value: $18,500 | Tier: Enterprise High-Value</text>
    <text y="198" fill="#fbbf24">[09:44:18] SENTINEL ROTATOR   ➜ Performing zero-cost RFC SMTP mailbox handshake...</text>
    <text y="220" fill="#94a3b8">             ✓ Verified Target: founders@candoriq.com (99.4% confidence score)</text>
    <text y="250" fill="#34d399">[09:44:20] CRM AUTOPILOT      ➜ Logged deal #653 into Kanban Board [Stage: Sourced]</text>
  </g>

  <g transform="translate(24, 350)">
    <rect width="852" height="86" rx="12" fill="#1e293b" fill-opacity="0.6" stroke="#6366f1" stroke-opacity="0.4"/>
    <circle cx="32" cy="43" r="16" fill="#6366f1" fill-opacity="0.2"/>
    <text x="26" y="48" fill="#818cf8" font-family="monospace" font-size="14">✓</text>
    <text x="60" y="36" fill="#ffffff" font-family="system-ui, sans-serif" font-size="14" font-weight="bold">Autonomous Swarm Loop Finished: 5 Prospects Qualified</text>
    <text x="60" y="58" fill="#94a3b8" font-family="system-ui, sans-serif" font-size="12">All 5 companies have custom 4-scene video pitches generated and added to the deal pipeline.</text>
    <rect x="700" y="26" width="130" height="34" rx="8" fill="#6366f1"/>
    <text x="725" y="48" fill="#ffffff" font-family="system-ui, sans-serif" font-size="12" font-weight="bold">Review in CRM</text>
  </g>
</svg>"""

# 3. Website Doctor Audit SVG
svg3 = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 900 460" width="900" height="460">
  <rect width="900" height="460" rx="16" fill="#090d16" stroke="#1e293b" stroke-width="2"/>
  
  <rect width="900" height="42" rx="16" fill="#0f172a"/>
  <text x="24" y="26" fill="#94a3b8" font-family="monospace" font-size="12">Website Doctor Forensic Diagnostic · Target: stripe.com</text>

  <g transform="translate(24, 60)">
    <rect width="270" height="160" rx="14" fill="#1e293b" fill-opacity="0.5" stroke="#f59e0b" stroke-opacity="0.4"/>
    <text x="20" y="36" fill="#94a3b8" font-family="system-ui, sans-serif" font-size="12" font-weight="bold">LARGEST CONTENTFUL PAINT</text>
    <text x="20" y="90" fill="#f59e0b" font-family="monospace" font-size="42" font-weight="800">3.4s</text>
    <text x="20" y="120" fill="#f59e0b" font-family="system-ui, sans-serif" font-size="11">Needs Optimization (&gt; 2.5s)</text>
    <text x="20" y="138" fill="#64748b" font-family="system-ui, sans-serif" font-size="10">High pitch leverage opportunity</text>
  </g>

  <g transform="translate(315, 60)">
    <rect width="270" height="160" rx="14" fill="#1e293b" fill-opacity="0.5" stroke="#10b981" stroke-opacity="0.4"/>
    <text x="20" y="36" fill="#94a3b8" font-family="system-ui, sans-serif" font-size="12" font-weight="bold">TIME TO FIRST BYTE (TTFB)</text>
    <text x="20" y="90" fill="#10b981" font-family="monospace" font-size="42" font-weight="800">180ms</text>
    <text x="20" y="120" fill="#10b981" font-family="system-ui, sans-serif" font-size="11">Good CDN Response (&lt; 200ms)</text>
    <text x="20" y="138" fill="#64748b" font-family="system-ui, sans-serif" font-size="10">AWS CloudFront / Edge pass</text>
  </g>

  <g transform="translate(606, 60)">
    <rect width="270" height="160" rx="14" fill="#1e293b" fill-opacity="0.5" stroke="#6366f1" stroke-opacity="0.4"/>
    <text x="20" y="36" fill="#94a3b8" font-family="system-ui, sans-serif" font-size="12" font-weight="bold">ESTIMATED MONTHLY LOSS</text>
    <text x="20" y="90" fill="#818cf8" font-family="monospace" font-size="42" font-weight="800">$8,400</text>
    <text x="20" y="120" fill="#818cf8" font-family="system-ui, sans-serif" font-size="11">Revenue Lost to Slow Mobile</text>
    <text x="20" y="138" fill="#64748b" font-family="system-ui, sans-serif" font-size="10">Based on estimated traffic &amp; AOV</text>
  </g>

  <g transform="translate(24, 240)">
    <rect width="852" height="190" rx="14" fill="#0f172a" stroke="#334155"/>
    <text x="24" y="32" fill="#ffffff" font-family="system-ui, sans-serif" font-size="14" font-weight="bold">Diagnostic Teardown Highlights &amp; Action Plan</text>
    
    <g transform="translate(24, 52)" font-family="system-ui, sans-serif" font-size="12">
      <text y="16" fill="#f87171">✗ Render-blocking CSS holding back first paint by 1.8 seconds.</text>
      <text y="40" fill="#fbbf24">⚠ Missing strict DMARC reject enforcement (spoofing vulnerability).</text>
      <text y="64" fill="#34d399">✓ TLS 1.3 encryption valid with HSTS header preloaded.</text>
      <text y="88" fill="#38bdf8">✓ Detected Stack: Next.js 14, React, Tailwind CSS, Stripe Elements, Datadog.</text>
    </g>

    <rect x="660" y="130" width="168" height="36" rx="8" fill="#10b981"/>
    <text x="680" y="153" fill="#ffffff" font-family="system-ui, sans-serif" font-size="12" font-weight="bold">1-Click Export Deck 📄</text>
  </g>
</svg>"""

# 4. Video Storyboard SVG
svg4 = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 900 460" width="900" height="460">
  <rect width="900" height="460" rx="16" fill="#090d16" stroke="#1e293b" stroke-width="2"/>
  <rect width="900" height="42" rx="16" fill="#0f172a"/>
  <text x="24" y="26" fill="#94a3b8" font-family="monospace" font-size="12">Multimodal Pitch Studio · 4-Scene Founder Video Script (60s Loom)</text>

  <g transform="translate(24, 60)">
    <rect width="200" height="360" rx="12" fill="#1e293b" fill-opacity="0.6" stroke="#6366f1" stroke-opacity="0.5"/>
    <rect x="12" y="12" width="176" height="24" rx="6" fill="#6366f1" fill-opacity="0.2"/>
    <text x="20" y="28" fill="#a5b4fc" font-family="monospace" font-size="11" font-weight="bold">SCENE 1 · 0-15s</text>
    <text x="16" y="60" fill="#ffffff" font-family="system-ui, sans-serif" font-size="13" font-weight="bold">The Hook</text>
    <text x="16" y="82" fill="#94a3b8" font-family="system-ui, sans-serif" font-size="11" font-weight="bold">Visual Direction:</text>
    <text x="16" y="98" fill="#64748b" font-family="system-ui, sans-serif" font-size="10">Record prospect hero loading on mobile 4G.</text>
    <rect x="12" y="130" width="176" height="170" rx="8" fill="#0f172a"/>
    <text x="20" y="150" fill="#cbd5e1" font-family="system-ui, sans-serif" font-size="11" font-style="italic">"Hi Sarah, noticed the mobile checkout on candoriq.com takes 4.1s to render on 4G networks..."</text>
  </g>

  <g transform="translate(242, 60)">
    <rect width="200" height="360" rx="12" fill="#1e293b" fill-opacity="0.6" stroke="#06b6d4" stroke-opacity="0.5"/>
    <rect x="12" y="12" width="176" height="24" rx="6" fill="#06b6d4" fill-opacity="0.2"/>
    <text x="20" y="28" fill="#67e8f9" font-family="monospace" font-size="11" font-weight="bold">SCENE 2 · 15-30s</text>
    <text x="16" y="60" fill="#ffffff" font-family="system-ui, sans-serif" font-size="13" font-weight="bold">The Evidence</text>
    <text x="16" y="82" fill="#94a3b8" font-family="system-ui, sans-serif" font-size="11" font-weight="bold">Visual Direction:</text>
    <text x="16" y="98" fill="#64748b" font-family="system-ui, sans-serif" font-size="10">Inspect waterfall showing 1.8s render-blocking CSS.</text>
    <rect x="12" y="130" width="176" height="170" rx="8" fill="#0f172a"/>
    <text x="20" y="150" fill="#cbd5e1" font-family="system-ui, sans-serif" font-size="11" font-style="italic">"Here is the exact stylesheet bundle delaying first paint for your signup funnel..."</text>
  </g>

  <g transform="translate(460, 60)">
    <rect width="200" height="360" rx="12" fill="#1e293b" fill-opacity="0.6" stroke="#a855f7" stroke-opacity="0.5"/>
    <rect x="12" y="12" width="176" height="24" rx="6" fill="#a855f7" fill-opacity="0.2"/>
    <text x="20" y="28" fill="#d8b4fe" font-family="monospace" font-size="11" font-weight="bold">SCENE 3 · 30-45s</text>
    <text x="16" y="60" fill="#ffffff" font-family="system-ui, sans-serif" font-size="13" font-weight="bold">The Proof</text>
    <text x="16" y="82" fill="#94a3b8" font-family="system-ui, sans-serif" font-size="11" font-weight="bold">Visual Direction:</text>
    <text x="16" y="98" fill="#64748b" font-family="system-ui, sans-serif" font-size="10">Show case study of 55% speedup on logistics client.</text>
    <rect x="12" y="130" width="176" height="170" rx="8" fill="#0f172a"/>
    <text x="20" y="150" fill="#cbd5e1" font-family="system-ui, sans-serif" font-size="11" font-style="italic">"We resolved this exact issue for an enterprise client, dropping page load to 1.1s..."</text>
  </g>

  <g transform="translate(678, 60)">
    <rect width="200" height="360" rx="12" fill="#1e293b" fill-opacity="0.6" stroke="#10b981" stroke-opacity="0.5"/>
    <rect x="12" y="12" width="176" height="24" rx="6" fill="#10b981" fill-opacity="0.2"/>
    <text x="20" y="28" fill="#6ee7b7" font-family="monospace" font-size="11" font-weight="bold">SCENE 4 · 45-60s</text>
    <text x="16" y="60" fill="#ffffff" font-family="system-ui, sans-serif" font-size="13" font-weight="bold">Call to Action</text>
    <text x="16" y="82" fill="#94a3b8" font-family="system-ui, sans-serif" font-size="11" font-weight="bold">Visual Direction:</text>
    <text x="16" y="98" fill="#64748b" font-family="system-ui, sans-serif" font-size="10">Camera on face, friendly low-friction close.</text>
    <rect x="12" y="130" width="176" height="170" rx="8" fill="#0f172a"/>
    <text x="20" y="150" fill="#cbd5e1" font-family="system-ui, sans-serif" font-size="11" font-style="italic">"Happy to share the full PDF teardown. Open to a short 5-minute conversation?"</text>
  </g>
</svg>"""

# 5. Kanban CRM SVG
svg5 = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 900 460" width="900" height="460">
  <rect width="900" height="460" rx="16" fill="#090d16" stroke="#1e293b" stroke-width="2"/>
  <rect width="900" height="42" rx="16" fill="#0f172a"/>
  <text x="24" y="26" fill="#94a3b8" font-family="monospace" font-size="12">Sovereign Revenue Kanban CRM · Pipeline Value: $148,000 · Won: $42,500</text>

  <g transform="translate(24, 60)">
    <rect width="200" height="370" rx="12" fill="#1e293b" fill-opacity="0.4" stroke="#334155"/>
    <text x="16" y="28" fill="#94a3b8" font-family="system-ui, sans-serif" font-size="12" font-weight="bold">1. SOURCED</text>
    <text x="150" y="28" fill="#64748b" font-family="monospace" font-size="11">12 deals</text>
    <rect x="12" y="44" width="176" height="70" rx="8" fill="#0f172a" stroke="#334155"/>
    <text x="20" y="68" fill="#ffffff" font-family="system-ui, sans-serif" font-size="12" font-weight="bold">Austin Dental Care</text>
    <text x="20" y="86" fill="#10b981" font-family="monospace" font-size="11">$4,500 · Site Rescue</text>
  </g>

  <g transform="translate(242, 60)">
    <rect width="200" height="370" rx="12" fill="#1e293b" fill-opacity="0.4" stroke="#0284c7" stroke-opacity="0.4"/>
    <text x="16" y="28" fill="#38bdf8" font-family="system-ui, sans-serif" font-size="12" font-weight="bold">2. AUDITED</text>
    <text x="150" y="28" fill="#64748b" font-family="monospace" font-size="11">6 deals</text>
    <rect x="12" y="44" width="176" height="70" rx="8" fill="#0f172a" stroke="#0284c7" stroke-opacity="0.4"/>
    <text x="20" y="68" fill="#ffffff" font-family="system-ui, sans-serif" font-size="12" font-weight="bold">CandorIQ, Inc.</text>
    <text x="20" y="86" fill="#10b981" font-family="monospace" font-size="11">$18,500 · Speedup</text>
  </g>

  <g transform="translate(460, 60)">
    <rect width="200" height="370" rx="12" fill="#1e293b" fill-opacity="0.4" stroke="#6366f1" stroke-opacity="0.4"/>
    <text x="16" y="28" fill="#818cf8" font-family="system-ui, sans-serif" font-size="12" font-weight="bold">5. PROPOSAL SENT</text>
    <text x="150" y="28" fill="#64748b" font-family="monospace" font-size="11">3 deals</text>
    <rect x="12" y="44" width="176" height="70" rx="8" fill="#0f172a" stroke="#6366f1" stroke-opacity="0.4"/>
    <text x="20" y="68" fill="#ffffff" font-family="system-ui, sans-serif" font-size="12" font-weight="bold">Beacon Cloud AI</text>
    <text x="20" y="86" fill="#10b981" font-family="monospace" font-size="11">$22,000 · SRE Pod</text>
  </g>

  <g transform="translate(678, 60)">
    <rect width="200" height="370" rx="12" fill="#10b981" fill-opacity="0.05" stroke="#10b981" stroke-opacity="0.5"/>
    <text x="16" y="28" fill="#34d399" font-family="system-ui, sans-serif" font-size="12" font-weight="bold">6. CLOSED WON</text>
    <text x="150" y="28" fill="#34d399" font-family="monospace" font-size="11">$42,500</text>
    <rect x="12" y="44" width="176" height="70" rx="8" fill="#064e3b" fill-opacity="0.4" stroke="#10b981" stroke-opacity="0.6"/>
    <text x="20" y="68" fill="#ffffff" font-family="system-ui, sans-serif" font-size="12" font-weight="bold">River Logistics</text>
    <text x="20" y="86" fill="#34d399" font-family="monospace" font-size="11">$24,000 · SIGNED!</text>
  </g>
</svg>"""

files = {
    'pipeline_architecture.svg': svg1,
    'swarm_simulation.svg': svg2,
    'website_doctor_audit.svg': svg3,
    'video_storyboard.svg': svg4,
    'kanban_crm.svg': svg5
}

for name, content in files.items():
    for d in dirs:
        p = os.path.join(d, name)
        with open(p, 'w') as fp:
            fp.write(content)
        print('Wrote', p)
