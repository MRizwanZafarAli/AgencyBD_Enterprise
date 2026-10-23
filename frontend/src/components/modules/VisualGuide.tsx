import { useState } from 'react';
import type { FC } from 'react';
import {
  BookOpen, ArrowRight, Sparkles,
  Bot, Stethoscope, Radar, Kanban,
  Video, Eye, Layers, Globe
} from 'lucide-react';
import type { TabType } from '../../types';

interface VisualGuideProps {
  setActiveTab: (t: TabType) => void;
}

export const VisualGuide: FC<VisualGuideProps> = ({ setActiveTab }) => {
  const [activeWorkflow, setActiveWorkflow] = useState<'quickstart' | 'doctor' | 'radar' | 'crm'>('quickstart');
  const [activeSimulation, setActiveSimulation] = useState<'swarm' | 'audit' | 'storyboard' | 'kanban'>('swarm');
  const [copiedKey, setCopiedKey] = useState(false);

  return (
    <div className="space-y-8 animate-fadeIn max-w-[1380px] mx-auto pb-12">
      {/* 1. Header Banner */}
      <div className="bento-tile specular-border rounded-3xl p-6 sm:p-8 bg-gradient-to-br from-indigo-950/40 via-slate-900/80 to-slate-950/80 border border-indigo-500/30 relative overflow-hidden">
        <div className="absolute right-0 top-0 bottom-0 w-1/3 bg-radial-gradient pointer-events-none opacity-20" />
        <div className="relative z-10 flex flex-col lg:flex-row lg:items-center justify-between gap-6">
          <div className="space-y-2 max-w-2xl">
            <div className="flex items-center space-x-2">
              <span className="px-3 py-1 rounded-full text-xs font-mono font-bold bg-indigo-500/20 text-indigo-300 border border-indigo-500/40 flex items-center gap-1.5">
                <Sparkles className="h-3.5 w-3.5 text-indigo-400" />
                <span>OFFICIAL PLATFORM USER MANUAL &amp; BLUEPRINT</span>
              </span>
              <span className="px-2.5 py-0.5 rounded-full text-xs font-mono bg-emerald-500/20 text-emerald-300 border border-emerald-500/40">
                100% Sovereign · $0 API Cost
              </span>
            </div>
            <h1 className="text-3xl sm:text-4xl font-black text-white tracking-tight">
              Simple, Autonomous Business Development
            </h1>
            <p className="text-sm text-slate-300 leading-relaxed">
              AgencyBD transforms hours of manual lead hunting, technical auditing, cold copy drafting, and CRM data entry into a <strong>single-click autonomous workflow</strong>. This guide walks you through every feature with interactive diagrams and visual simulations.
            </p>
          </div>

          <div className="flex flex-wrap sm:flex-nowrap gap-3 shrink-0">
            <button
              onClick={() => setActiveTab('autopilot')}
              className="px-5 py-3 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-bold flex items-center gap-2 shadow-lg shadow-indigo-600/30 transition hover:scale-[1.02]"
            >
              <Bot className="h-4 w-4" />
              <span>Launch Swarm Auto-Pilot</span>
            </button>
            <button
              onClick={() => setActiveTab('doctor')}
              className="px-5 py-3 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 text-xs font-semibold flex items-center gap-2 transition"
            >
              <Stethoscope className="h-4 w-4 text-emerald-400" />
              <span>Audit a Prospect Website</span>
            </button>
          </div>
        </div>
      </div>

      {/* 2. Interactive End-to-End Autonomous Pipeline Diagram */}
      <div className="bento-tile specular-border rounded-2xl p-6 sm:p-7 space-y-5">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-b border-slate-800/80 pb-4">
          <div>
            <h2 className="text-lg font-bold text-white flex items-center gap-2">
              <Layers className="h-5 w-5 text-indigo-400" />
              <span>Autonomous Pipeline Architecture: How Data Flows</span>
            </h2>
            <p className="text-xs text-slate-400 mt-0.5">
              Click on any step below to jump directly into that module or inspect its function.
            </p>
          </div>
          <span className="text-[11px] font-mono text-slate-400">Click any step to navigate</span>
        </div>

        {/* Render High-Resolution Architecture SVG Diagram */}
        <div className="rounded-2xl overflow-hidden border border-slate-800/80 bg-slate-950/80 shadow-2xl">
          <img
            src="/images/pipeline_architecture.svg"
            alt="Multi-Agent Pipeline Architecture"
            className="w-full h-auto block"
          />
        </div>

        {/* 5-Stage Visual Workflow Cards */}
        <div className="grid grid-cols-1 md:grid-cols-5 gap-3.5 pt-2">
          {/* Step 1 */}
          <div
            onClick={() => setActiveTab('hunt')}
            className="bento-tile-interactive specular-border rounded-xl p-4 bg-slate-900/60 border border-slate-800 hover:border-indigo-500/60 transition cursor-pointer group flex flex-col justify-between space-y-3"
          >
            <div>
              <div className="flex items-center justify-between">
                <span className="w-6 h-6 rounded-lg bg-indigo-500/20 text-indigo-400 text-xs font-bold flex items-center justify-center font-mono">1</span>
                <Globe className="h-4 w-4 text-indigo-400 group-hover:scale-110 transition-transform" />
              </div>
              <h3 className="text-xs font-bold text-white mt-2 group-hover:text-indigo-300 transition">Lead Discovery</h3>
              <p className="text-[11px] text-slate-400 mt-1 leading-snug">
                Scrapes SEC Form D, OpenStreetMap local businesses, Upwork, and GitHub Bounties.
              </p>
            </div>
            <div className="text-[10px] font-mono text-indigo-400 flex items-center gap-1 group-hover:translate-x-1 transition-transform">
              <span>Open Hunter</span>
              <ArrowRight className="h-3 w-3" />
            </div>
          </div>

          {/* Step 2 */}
          <div
            onClick={() => setActiveTab('doctor')}
            className="bento-tile-interactive specular-border rounded-xl p-4 bg-slate-900/60 border border-slate-800 hover:border-emerald-500/60 transition cursor-pointer group flex flex-col justify-between space-y-3"
          >
            <div>
              <div className="flex items-center justify-between">
                <span className="w-6 h-6 rounded-lg bg-emerald-500/20 text-emerald-400 text-xs font-bold flex items-center justify-center font-mono">2</span>
                <Stethoscope className="h-4 w-4 text-emerald-400 group-hover:scale-110 transition-transform" />
              </div>
              <h3 className="text-xs font-bold text-white mt-2 group-hover:text-emerald-300 transition">Technical Audit</h3>
              <p className="text-[11px] text-slate-400 mt-1 leading-snug">
                Measures LCP speed, SSL security, SEO tags, and tech stack in 2 seconds.
              </p>
            </div>
            <div className="text-[10px] font-mono text-emerald-400 flex items-center gap-1 group-hover:translate-x-1 transition-transform">
              <span>Open Doctor</span>
              <ArrowRight className="h-3 w-3" />
            </div>
          </div>

          {/* Step 3 */}
          <div
            onClick={() => setActiveTab('multimodal')}
            className="bento-tile-interactive specular-border rounded-xl p-4 bg-slate-900/60 border border-slate-800 hover:border-purple-500/60 transition cursor-pointer group flex flex-col justify-between space-y-3"
          >
            <div>
              <div className="flex items-center justify-between">
                <span className="w-6 h-6 rounded-lg bg-purple-500/20 text-purple-400 text-xs font-bold flex items-center justify-center font-mono">3</span>
                <Video className="h-4 w-4 text-purple-400 group-hover:scale-110 transition-transform" />
              </div>
              <h3 className="text-xs font-bold text-white mt-2 group-hover:text-purple-300 transition">Pitch Synthesis</h3>
              <p className="text-[11px] text-slate-400 mt-1 leading-snug">
                Generates a 4-scene video script &amp; Lavender 90+ cold email citing real audit metrics.
              </p>
            </div>
            <div className="text-[10px] font-mono text-purple-400 flex items-center gap-1 group-hover:translate-x-1 transition-transform">
              <span>Open Studio</span>
              <ArrowRight className="h-3 w-3" />
            </div>
          </div>

          {/* Step 4 */}
          <div
            onClick={() => setActiveTab('autopilot')}
            className="bento-tile-interactive specular-border rounded-xl p-4 bg-slate-900/60 border border-slate-800 hover:border-cyan-500/60 transition cursor-pointer group flex flex-col justify-between space-y-3"
          >
            <div>
              <div className="flex items-center justify-between">
                <span className="w-6 h-6 rounded-lg bg-cyan-500/20 text-cyan-400 text-xs font-bold flex items-center justify-center font-mono">4</span>
                <Bot className="h-4 w-4 text-cyan-400 group-hover:scale-110 transition-transform" />
              </div>
              <h3 className="text-xs font-bold text-white mt-2 group-hover:text-cyan-300 transition">Autonomous Swarm</h3>
              <p className="text-[11px] text-slate-400 mt-1 leading-snug">
                Multi-agent swarm automatically scores close probability &amp; queues personalized outreach.
              </p>
            </div>
            <div className="text-[10px] font-mono text-cyan-400 flex items-center gap-1 group-hover:translate-x-1 transition-transform">
              <span>Open Auto-Pilot</span>
              <ArrowRight className="h-3 w-3" />
            </div>
          </div>

          {/* Step 5 */}
          <div
            onClick={() => setActiveTab('portfolio')}
            className="bento-tile-interactive specular-border rounded-xl p-4 bg-slate-900/60 border border-slate-800 hover:border-amber-500/60 transition cursor-pointer group flex flex-col justify-between space-y-3"
          >
            <div>
              <div className="flex items-center justify-between">
                <span className="w-6 h-6 rounded-lg bg-amber-500/20 text-amber-400 text-xs font-bold flex items-center justify-center font-mono">5</span>
                <Kanban className="h-4 w-4 text-amber-400 group-hover:scale-110 transition-transform" />
              </div>
              <h3 className="text-xs font-bold text-white mt-2 group-hover:text-amber-300 transition">Revenue CRM</h3>
              <p className="text-[11px] text-slate-400 mt-1 leading-snug">
                Track deals from Sourced $\rightarrow$ Proposal Sent $\rightarrow$ Closed Won in a sovereign Kanban board.
              </p>
            </div>
            <div className="text-[10px] font-mono text-amber-400 flex items-center gap-1 group-hover:translate-x-1 transition-transform">
              <span>Open CRM</span>
              <ArrowRight className="h-3 w-3" />
            </div>
          </div>
        </div>
      </div>

      {/* 3. Animated Visual Simulated Screens (Simulating Video/GIF Walkthroughs) */}
      <div className="bento-tile specular-border rounded-2xl p-6 sm:p-7 space-y-6">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-slate-800/80 pb-4">
          <div>
            <h2 className="text-lg font-bold text-white flex items-center gap-2">
              <Eye className="h-5 w-5 text-indigo-400" />
              <span>Animated Visual Simulations (Feature Walkthroughs)</span>
            </h2>
            <p className="text-xs text-slate-400 mt-0.5">
              Simulated live GIF/video previews demonstrating key autonomous capabilities in action.
            </p>
          </div>

          {/* Simulation Selector Pills */}
          <div className="flex items-center gap-1.5 p-1 rounded-xl bg-slate-900 border border-slate-800">
            <button
              onClick={() => setActiveSimulation('swarm')}
              className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition ${
                activeSimulation === 'swarm' ? 'bg-indigo-600 text-white shadow-sm' : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              1. Swarm Execution
            </button>
            <button
              onClick={() => setActiveSimulation('audit')}
              className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition ${
                activeSimulation === 'audit' ? 'bg-indigo-600 text-white shadow-sm' : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              2. Website Teardown
            </button>
            <button
              onClick={() => setActiveSimulation('storyboard')}
              className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition ${
                activeSimulation === 'storyboard' ? 'bg-indigo-600 text-white shadow-sm' : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              3. Video Storyboard
            </button>
            <button
              onClick={() => setActiveSimulation('kanban')}
              className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition ${
                activeSimulation === 'kanban' ? 'bg-indigo-600 text-white shadow-sm' : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              4. Revenue Kanban
            </button>
          </div>
        </div>

        {/* Simulation 1: Swarm Execution */}
        {activeSimulation === 'swarm' && (
          <div className="rounded-2xl border border-slate-800 bg-slate-950/90 p-5 space-y-4">
            <div className="flex items-center justify-between text-xs text-slate-400 border-b border-slate-800 pb-2.5">
              <div className="flex items-center gap-2">
                <span className="w-2.5 h-2.5 rounded-full bg-emerald-400 animate-pulse" />
                <span className="font-mono text-emerald-400 font-bold">SIMULATED EXECUTION: Multi-Agent Swarm Autopilot</span>
              </div>
              <span className="font-mono text-[11px] text-slate-500">Live Agent Handshakes</span>
            </div>

            <div className="rounded-xl overflow-hidden border border-slate-800 shadow-xl">
              <img
                src="/images/swarm_simulation.svg"
                alt="Swarm Execution Preview"
                className="w-full h-auto block"
              />
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
              {/* Terminal Logs Simulation */}
              <div className="lg:col-span-2 bg-slate-900/90 rounded-xl p-4 font-mono text-[12px] space-y-2 border border-slate-800/80 max-h-72 overflow-y-auto">
                <div className="text-cyan-400 font-semibold">[09:42:01] SOURCING SCOUT $\rightarrow$ Ingesting SEC EDGAR Form D venture filings...</div>
                <div className="text-slate-300">   ✓ Resolved 5 companies with recent Series A funding ($3M - $12M).</div>
                <div className="text-indigo-400 font-semibold mt-1">[09:42:03] FORENSICS ENGINEER $\rightarrow$ Crawling target infrastructure...</div>
                <div className="text-slate-300">   ✓ Target: candoriq.com | LCP: 4.1s (HIGH URGENCY) | React 18, AWS CloudFront</div>
                <div className="text-purple-400 font-semibold mt-1">[09:42:05] STRATEGIST CO-PILOT $\rightarrow$ Calculating mathematical win probability...</div>
                <div className="text-emerald-400 font-bold">   ✓ Fit Score: 94% | Expected Deal Value: $18,500 | Tier: Enterprise High-Value</div>
                <div className="text-amber-400 font-semibold mt-1">[09:42:07] DELIVERABILITY SENTINEL $\rightarrow$ Encoding RFC-compliant mail permutations...</div>
                <div className="text-slate-300">   ✓ Verified Mailbox: founders@candoriq.com (99.2% SMTP confidence score)</div>
                <div className="text-emerald-400 font-semibold mt-1">[09:42:09] CRM ENGINE $\rightarrow$ Logged deal #653 into Kanban Pipeline [Stage: Sourced]</div>
              </div>

              {/* Live Status Card */}
              <div className="bento-tile specular-border rounded-xl p-4 space-y-3 bg-slate-900/50 border border-indigo-500/30 flex flex-col justify-between">
                <div>
                  <span className="text-[10px] font-mono font-bold text-indigo-400 uppercase tracking-wider">Automated Output</span>
                  <h4 className="text-sm font-bold text-white mt-1">CandorIQ, Inc.</h4>
                  <div className="mt-2 space-y-1 text-xs text-slate-300">
                    <div className="flex justify-between"><span>Deal Value:</span><strong className="text-emerald-400 font-mono">$18,500</strong></div>
                    <div className="flex justify-between"><span>Win Probability:</span><strong className="text-cyan-400 font-mono">94%</strong></div>
                    <div className="flex justify-between"><span>Status:</span><span className="text-amber-400 font-mono">Queued for Review</span></div>
                  </div>
                </div>
                <button
                  onClick={() => setActiveTab('autopilot')}
                  className="w-full py-2 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-semibold transition"
                >
                  Run Live in Swarm Autopilot $\rightarrow$
                </button>
              </div>
            </div>
          </div>
        )}

        {/* Simulation 2: Website Teardown */}
        {activeSimulation === 'audit' && (
          <div className="rounded-2xl border border-slate-800 bg-slate-950/90 p-5 space-y-4">
            <div className="flex items-center justify-between text-xs text-slate-400 border-b border-slate-800 pb-2.5">
              <div className="flex items-center gap-2">
                <span className="w-2.5 h-2.5 rounded-full bg-cyan-400 animate-pulse" />
                <span className="font-mono text-cyan-400 font-bold">SIMULATED AUDIT: Website Doctor Diagnostic</span>
              </div>
              <span className="font-mono text-[11px] text-slate-500">Target: stripe.com</span>
            </div>

            <div className="rounded-xl overflow-hidden border border-slate-800 shadow-xl">
              <img
                src="/images/website_doctor_audit.svg"
                alt="Website Doctor Diagnostic Preview"
                className="w-full h-auto block"
              />
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
              <div className="p-4 rounded-xl bg-slate-900 border border-slate-800 text-center space-y-1">
                <div className="text-xs text-slate-400 font-medium">Largest Contentful Paint</div>
                <div className="text-3xl font-black font-mono text-amber-400">3.4s</div>
                <div className="text-[11px] text-slate-400">Needs Optimization (&gt;2.5s)</div>
              </div>

              <div className="p-4 rounded-xl bg-slate-900 border border-slate-800 text-center space-y-1">
                <div className="text-xs text-slate-400 font-medium">Time to First Byte</div>
                <div className="text-3xl font-black font-mono text-emerald-400">180ms</div>
                <div className="text-[11px] text-emerald-400/80">Excellent Edge CDN Pass</div>
              </div>

              <div className="p-4 rounded-xl bg-slate-900 border border-slate-800 text-center space-y-1">
                <div className="text-xs text-slate-400 font-medium">Pitch Leverage Hook</div>
                <div className="text-sm font-bold text-indigo-300 pt-1">Mobile 4G Degradation</div>
                <div className="text-[11px] text-slate-400">Cut bounce rate by 34%</div>
              </div>
            </div>

            <div className="p-3.5 rounded-xl bg-indigo-950/30 border border-indigo-500/20 flex flex-col sm:flex-row sm:items-center justify-between gap-3 text-xs">
              <span className="text-slate-300">
                <strong>Executive Pitch Ready:</strong> 1-Click generated HTML Teardown Deck with before/after visual charts.
              </span>
              <button
                onClick={() => setActiveTab('doctor')}
                className="px-4 py-2 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white font-semibold shrink-0 transition"
              >
                Audit Any Website Now $\rightarrow$
              </button>
            </div>
          </div>
        )}

        {/* Simulation 3: Video Storyboard */}
        {activeSimulation === 'storyboard' && (
          <div className="rounded-2xl border border-slate-800 bg-slate-950/90 p-5 space-y-4">
            <div className="flex items-center justify-between text-xs text-slate-400 border-b border-slate-800 pb-2.5">
              <div className="flex items-center gap-2">
                <span className="w-2.5 h-2.5 rounded-full bg-purple-400 animate-pulse" />
                <span className="font-mono text-purple-400 font-bold">SIMULATED LOOM SCRIPT: 4-Scene Founder Teardown</span>
              </div>
              <span className="font-mono text-[11px] text-purple-400 font-bold">Total Duration: 60 Seconds</span>
            </div>

            <div className="rounded-xl overflow-hidden border border-slate-800 shadow-xl">
              <img
                src="/images/video_storyboard.svg"
                alt="Video Storyboard Preview"
                className="w-full h-auto block"
              />
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
              <div className="p-3.5 rounded-xl bg-slate-900 border border-slate-800 space-y-2 text-xs">
                <div className="flex justify-between font-bold text-indigo-300"><span>Scene 1: Hook</span><span className="text-slate-500 font-mono">0-15s</span></div>
                <div className="text-[11px] text-slate-400"><strong>Visual:</strong> Screen record prospect hero section loading slowly.</div>
                <div className="text-[11px] italic text-slate-300 bg-slate-950 p-2 rounded border border-slate-800/80">
                  "Hi Sarah, noticed your mobile checkout has a 3.4s delay on 4G networks..."
                </div>
              </div>

              <div className="p-3.5 rounded-xl bg-slate-900 border border-slate-800 space-y-2 text-xs">
                <div className="flex justify-between font-bold text-cyan-300"><span>Scene 2: Evidence</span><span className="text-slate-500 font-mono">15-30s</span></div>
                <div className="text-[11px] text-slate-400"><strong>Visual:</strong> Inspect network waterfall showing render-blocking CSS.</div>
                <div className="text-[11px] italic text-slate-300 bg-slate-950 p-2 rounded border border-slate-800/80">
                  "Here is the exact stylesheet holding back first meaningful paint..."
                </div>
              </div>

              <div className="p-3.5 rounded-xl bg-slate-900 border border-slate-800 space-y-2 text-xs">
                <div className="flex justify-between font-bold text-purple-300"><span>Scene 3: Proof</span><span className="text-slate-500 font-mono">30-45s</span></div>
                <div className="text-[11px] text-slate-400"><strong>Visual:</strong> Show verified case study of 55% speed increase.</div>
                <div className="text-[11px] italic text-slate-300 bg-slate-950 p-2 rounded border border-slate-800/80">
                  "We solved this exact bottleneck for an enterprise logistics client..."
                </div>
              </div>

              <div className="p-3.5 rounded-xl bg-slate-900 border border-slate-800 space-y-2 text-xs">
                <div className="flex justify-between font-bold text-emerald-300"><span>Scene 4: Call to Action</span><span className="text-slate-500 font-mono">45-60s</span></div>
                <div className="text-[11px] text-slate-400"><strong>Visual:</strong> Face camera with friendly low-friction close.</div>
                <div className="text-[11px] italic text-slate-300 bg-slate-950 p-2 rounded border border-slate-800/80">
                  "Happy to send over the full PDF diagnostic if helpful. Open to a 5-min chat?"
                </div>
              </div>
            </div>

            <div className="flex justify-end">
              <button
                onClick={() => setActiveTab('multimodal')}
                className="px-4 py-2 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-semibold transition"
              >
                Synthesize Live Video Pitch $\rightarrow$
              </button>
            </div>
          </div>
        )}

        {/* Simulation 4: Revenue Kanban */}
        {activeSimulation === 'kanban' && (
          <div className="rounded-2xl border border-slate-800 bg-slate-950/90 p-5 space-y-4">
            <div className="flex items-center justify-between text-xs text-slate-400 border-b border-slate-800 pb-2.5">
              <div className="flex items-center gap-2">
                <span className="w-2.5 h-2.5 rounded-full bg-amber-400 animate-pulse" />
                <span className="font-mono text-amber-400 font-bold">SIMULATED CRM: Visual Revenue Pipeline</span>
              </div>
              <span className="font-mono text-emerald-400 font-bold">Closed Won Revenue: $42,500</span>
            </div>

            <div className="rounded-xl overflow-hidden border border-slate-800 shadow-xl">
              <img
                src="/images/kanban_crm.svg"
                alt="Revenue Kanban CRM Preview"
                className="w-full h-auto block"
              />
            </div>

            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-xs">
              <div className="p-3.5 rounded-xl bg-slate-900 border border-slate-800 space-y-2">
                <div className="font-bold text-slate-300 flex justify-between"><span>1. Sourced</span><span className="font-mono text-slate-500">12 deals</span></div>
                <div className="p-2 rounded-lg bg-slate-950 border border-slate-800/80 text-[11px]">
                  <div className="font-semibold text-white">Austin Dental Care</div>
                  <div className="text-emerald-400 font-mono text-[10px]">$4,500 Presence Rescue</div>
                </div>
              </div>

              <div className="p-3.5 rounded-xl bg-sky-950/20 border border-sky-500/30 space-y-2">
                <div className="font-bold text-sky-300 flex justify-between"><span>2. Audited</span><span className="font-mono text-slate-500">6 deals</span></div>
                <div className="p-2 rounded-lg bg-slate-950 border border-slate-800/80 text-[11px]">
                  <div className="font-semibold text-white">Acme FinTech</div>
                  <div className="text-emerald-400 font-mono text-[10px]">$12,000 LCP Speedup</div>
                </div>
              </div>

              <div className="p-3.5 rounded-xl bg-indigo-950/20 border border-indigo-500/30 space-y-2">
                <div className="font-bold text-indigo-300 flex justify-between"><span>5. Proposal Sent</span><span className="font-mono text-slate-500">3 deals</span></div>
                <div className="p-2 rounded-lg bg-slate-950 border border-slate-800/80 text-[11px]">
                  <div className="font-semibold text-white">Beacon Cloud</div>
                  <div className="text-emerald-400 font-mono text-[10px]">$18,500 SRE Pod</div>
                </div>
              </div>

              <div className="p-3.5 rounded-xl bg-emerald-950/20 border border-emerald-500/40 space-y-2">
                <div className="font-bold text-emerald-300 flex justify-between"><span>6. Closed Won 🏆</span><span className="font-mono text-emerald-400 font-bold">$42,500</span></div>
                <div className="p-2 rounded-lg bg-slate-950 border border-emerald-500/30 text-[11px]">
                  <div className="font-semibold text-white">River Logistics</div>
                  <div className="text-emerald-400 font-mono text-[10px]">$24,000 Signed!</div>
                </div>
              </div>
            </div>

            <div className="flex justify-end">
              <button
                onClick={() => setActiveTab('portfolio')}
                className="px-4 py-2 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-semibold transition"
              >
                Open Sovereign Kanban CRM $\rightarrow$
              </button>
            </div>
          </div>
        )}
      </div>

      {/* 4. Actionable 1-2-3 Step-by-Step Guides for Any User */}
      <div className="bento-tile specular-border rounded-2xl p-6 sm:p-7 space-y-6">
        <div className="border-b border-slate-800/80 pb-4">
          <h2 className="text-lg font-bold text-white flex items-center gap-2">
            <BookOpen className="h-5 w-5 text-indigo-400" />
            <span>Step-by-Step Practical Guides: What to Click and When</span>
          </h2>
          <p className="text-xs text-slate-400 mt-0.5">
            Select a common goal below to see the exact 1-2-3 steps with zero guesswork.
          </p>
        </div>

        {/* Tab Switcher */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
          <button
            onClick={() => setActiveWorkflow('quickstart')}
            className={`p-3 rounded-xl border text-xs font-semibold text-left transition flex items-center gap-2 ${
              activeWorkflow === 'quickstart'
                ? 'bg-indigo-600/20 text-indigo-200 border-indigo-500/50 shadow-sm'
                : 'bg-slate-900 border-slate-800 text-slate-400 hover:text-white'
            }`}
          >
            <Bot className="h-4 w-4 shrink-0 text-indigo-400" />
            <span>A. 60-Sec Auto Campaign</span>
          </button>

          <button
            onClick={() => setActiveWorkflow('doctor')}
            className={`p-3 rounded-xl border text-xs font-semibold text-left transition flex items-center gap-2 ${
              activeWorkflow === 'doctor'
                ? 'bg-emerald-600/20 text-emerald-200 border-emerald-500/50 shadow-sm'
                : 'bg-slate-900 border-slate-800 text-slate-400 hover:text-white'
            }`}
          >
            <Stethoscope className="h-4 w-4 shrink-0 text-emerald-400" />
            <span>B. 1-Click Site Audit</span>
          </button>

          <button
            onClick={() => setActiveWorkflow('radar')}
            className={`p-3 rounded-xl border text-xs font-semibold text-left transition flex items-center gap-2 ${
              activeWorkflow === 'radar'
                ? 'bg-cyan-600/20 text-cyan-200 border-cyan-500/50 shadow-sm'
                : 'bg-slate-900 border-slate-800 text-slate-400 hover:text-white'
            }`}
          >
            <Radar className="h-4 w-4 shrink-0 text-cyan-400" />
            <span>C. Live Bids &amp; Bounties</span>
          </button>

          <button
            onClick={() => setActiveWorkflow('crm')}
            className={`p-3 rounded-xl border text-xs font-semibold text-left transition flex items-center gap-2 ${
              activeWorkflow === 'crm'
                ? 'bg-amber-600/20 text-amber-200 border-amber-500/50 shadow-sm'
                : 'bg-slate-900 border-slate-800 text-slate-400 hover:text-white'
            }`}
          >
            <Kanban className="h-4 w-4 shrink-0 text-amber-400" />
            <span>D. Track Deals to Won</span>
          </button>
        </div>

        {/* Workflow Detail A */}
        {activeWorkflow === 'quickstart' && (
          <div className="space-y-4 pt-2">
            <div className="p-4 rounded-xl bg-indigo-950/20 border border-indigo-500/30 flex items-start gap-3">
              <span className="p-2 rounded-lg bg-indigo-600/20 text-indigo-400 font-mono font-bold text-sm">A</span>
              <div className="space-y-1">
                <h3 className="text-sm font-bold text-white">How to Run a 60-Second Autonomous Campaign</h3>
                <p className="text-xs text-slate-300">
                  The Swarm Auto-Pilot coordinates 4 specialist agents: Sourcing Scout, Forensics Engineer, Deal Strategist, and Deliverability Sentinel.
                </p>
              </div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
              <div className="p-4 rounded-xl bg-slate-900 border border-slate-800 space-y-2">
                <div className="text-xs font-bold text-indigo-400 font-mono">STEP 1</div>
                <h4 className="text-xs font-bold text-white">Choose Target Channel</h4>
                <p className="text-xs text-slate-400 leading-relaxed">
                  Go to <strong>Swarm Auto-Pilot</strong>. Choose <em>SEC EDGAR Form D</em> (newly funded venture startups) or <em>Local Businesses</em>.
                </p>
              </div>

              <div className="p-4 rounded-xl bg-slate-900 border border-slate-800 space-y-2">
                <div className="text-xs font-bold text-indigo-400 font-mono">STEP 2</div>
                <h4 className="text-xs font-bold text-white">Click "Launch Auto-Pilot"</h4>
                <p className="text-xs text-slate-400 leading-relaxed">
                  The agents crawl target websites, measure LCP Core Web Vitals, compute win probability, and generate verified email permutations.
                </p>
              </div>

              <div className="p-4 rounded-xl bg-slate-900 border border-slate-800 space-y-2">
                <div className="text-xs font-bold text-indigo-400 font-mono">STEP 3</div>
                <h4 className="text-xs font-bold text-white">Review &amp; Approve</h4>
                <p className="text-xs text-slate-400 leading-relaxed">
                  Review generated email hooks citing real audit metrics. Click 1 button to enroll into an outbound cadence or sync into the CRM.
                </p>
              </div>
            </div>

            <button
              onClick={() => setActiveTab('autopilot')}
              className="px-5 py-2.5 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-bold flex items-center gap-2 transition"
            >
              <span>Go to Swarm Auto-Pilot Now</span>
              <ArrowRight className="h-4 w-4" />
            </button>
          </div>
        )}

        {/* Workflow Detail B */}
        {activeWorkflow === 'doctor' && (
          <div className="space-y-4 pt-2">
            <div className="p-4 rounded-xl bg-emerald-950/20 border border-emerald-500/30 flex items-start gap-3">
              <span className="p-2 rounded-lg bg-emerald-600/20 text-emerald-400 font-mono font-bold text-sm">B</span>
              <div className="space-y-1">
                <h3 className="text-sm font-bold text-white">How to Audit Any Website &amp; Generate a 1-Click Pitch Deck</h3>
                <p className="text-xs text-slate-300">
                  Website Doctor runs an enterprise technical diagnostic in seconds, identifying slow page load, broken SSL/security headers, and missing SEO tags.
                </p>
              </div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
              <div className="p-4 rounded-xl bg-slate-900 border border-slate-800 space-y-2">
                <div className="text-xs font-bold text-emerald-400 font-mono">STEP 1</div>
                <h4 className="text-xs font-bold text-white">Type Any Domain</h4>
                <p className="text-xs text-slate-400 leading-relaxed">
                  Enter any website URL or domain (e.g. <code>stripe.com</code> or <code>acmedental.com</code>) into the input box.
                </p>
              </div>

              <div className="p-4 rounded-xl bg-slate-900 border border-slate-800 space-y-2">
                <div className="text-xs font-bold text-emerald-400 font-mono">STEP 2</div>
                <h4 className="text-xs font-bold text-white">Click "Run Comprehensive Audit"</h4>
                <p className="text-xs text-slate-400 leading-relaxed">
                  The sovereign diagnostic engine measures LCP speed, TTFB server response, security headers, and technologies used.
                </p>
              </div>

              <div className="p-4 rounded-xl bg-slate-900 border border-slate-800 space-y-2">
                <div className="text-xs font-bold text-emerald-400 font-mono">STEP 3</div>
                <h4 className="text-xs font-bold text-white">Bridge to Pitch Studio</h4>
                <p className="text-xs text-slate-400 leading-relaxed">
                  Click <strong>"Bridge to Pitch Studio"</strong> to automatically generate a 4-scene video script or export a presentation slide deck!
                </p>
              </div>
            </div>

            <button
              onClick={() => setActiveTab('doctor')}
              className="px-5 py-2.5 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-bold flex items-center gap-2 transition"
            >
              <span>Go to Website Doctor Now</span>
              <ArrowRight className="h-4 w-4" />
            </button>
          </div>
        )}

        {/* Workflow Detail C */}
        {activeWorkflow === 'radar' && (
          <div className="space-y-4 pt-2">
            <div className="p-4 rounded-xl bg-cyan-950/20 border border-cyan-500/30 flex items-start gap-3">
              <span className="p-2 rounded-lg bg-cyan-600/20 text-cyan-400 font-mono font-bold text-sm">C</span>
              <div className="space-y-1">
                <h3 className="text-sm font-bold text-white">How to Win Bids, RFPs &amp; Bounties on the Radar</h3>
                <p className="text-xs text-slate-300">
                  Opportunity Radar continuously aggregates high-budget bids ($500 - $25,000+) from Upwork, GitHub Bounties, and EU/US government tenders.
                </p>
              </div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
              <div className="p-4 rounded-xl bg-slate-900 border border-slate-800 space-y-2">
                <div className="text-xs font-bold text-cyan-400 font-mono">STEP 1</div>
                <h4 className="text-xs font-bold text-white">Filter by Service &amp; Budget</h4>
                <p className="text-xs text-slate-400 leading-relaxed">
                  Browse opportunities ranked by <em>Fit Score</em>. Consumer low-budget micro-tasks are automatically filtered out.
                </p>
              </div>

              <div className="p-4 rounded-xl bg-slate-900 border border-slate-800 space-y-2">
                <div className="text-xs font-bold text-cyan-400 font-mono">STEP 2</div>
                <h4 className="text-xs font-bold text-white">Click "Draft Proposal"</h4>
                <p className="text-xs text-slate-400 leading-relaxed">
                  The zero-hallucination proposal studio cites your verified case studies and priced service offerings verbatim.
                </p>
              </div>

              <div className="p-4 rounded-xl bg-slate-900 border border-slate-800 space-y-2">
                <div className="text-xs font-bold text-cyan-400 font-mono">STEP 3</div>
                <h4 className="text-xs font-bold text-white">Submit &amp; Track</h4>
                <p className="text-xs text-slate-400 leading-relaxed">
                  Click the external link to submit your bid. When the client responds, mark the proposal as won in your CRM!
                </p>
              </div>
            </div>

            <button
              onClick={() => setActiveTab('radar')}
              className="px-5 py-2.5 rounded-xl bg-cyan-600 hover:bg-cyan-500 text-white text-xs font-bold flex items-center gap-2 transition"
            >
              <span>Go to Opportunity Radar Now</span>
              <ArrowRight className="h-4 w-4" />
            </button>
          </div>
        )}

        {/* Workflow Detail D */}
        {activeWorkflow === 'crm' && (
          <div className="space-y-4 pt-2">
            <div className="p-4 rounded-xl bg-amber-950/20 border border-amber-500/30 flex items-start gap-3">
              <span className="p-2 rounded-lg bg-amber-600/20 text-amber-400 font-mono font-bold text-sm">D</span>
              <div className="space-y-1">
                <h3 className="text-sm font-bold text-white">How to Track Deals to Closed-Won in the Sovereign CRM</h3>
                <p className="text-xs text-slate-300">
                  Every deal discovered by the hunter or radar is automatically stored in a sovereign SQLite CRM with 6 visual stages.
                </p>
              </div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
              <div className="p-4 rounded-xl bg-slate-900 border border-slate-800 space-y-2">
                <div className="text-xs font-bold text-amber-400 font-mono">STEP 1</div>
                <h4 className="text-xs font-bold text-white">View Deal Pipeline</h4>
                <p className="text-xs text-slate-400 leading-relaxed">
                  Go to <strong>Deal Pipeline &amp; CRM</strong>. See total pipeline value, weighted expected revenue, and deal counts across all 6 stages.
                </p>
              </div>

              <div className="p-4 rounded-xl bg-slate-900 border border-slate-800 space-y-2">
                <div className="text-xs font-bold text-amber-400 font-mono">STEP 2</div>
                <h4 className="text-xs font-bold text-white">Advance Deal Stages</h4>
                <p className="text-xs text-slate-400 leading-relaxed">
                  Click the arrow buttons on any card to move deals forward as meetings are booked and proposals sent.
                </p>
              </div>

              <div className="p-4 rounded-xl bg-slate-900 border border-slate-800 space-y-2">
                <div className="text-xs font-bold text-amber-400 font-mono">STEP 3</div>
                <h4 className="text-xs font-bold text-white">1-Click "Won" Calibration</h4>
                <p className="text-xs text-slate-400 leading-relaxed">
                  Click the <strong>"🏆 Won"</strong> button when a contract closes. This updates your revenue total and automatically calibrates future win scoring!
                </p>
              </div>
            </div>

            <button
              onClick={() => setActiveTab('portfolio')}
              className="px-5 py-2.5 rounded-xl bg-amber-600 hover:bg-amber-500 text-white text-xs font-bold flex items-center gap-2 transition"
            >
              <span>Go to Sovereign CRM Now</span>
              <ArrowRight className="h-4 w-4" />
            </button>
          </div>
        )}
      </div>

      {/* 5. Master API Key Quick Reference */}
      <div className="bento-tile specular-border rounded-2xl p-5 sm:p-6 bg-slate-900/60 border border-slate-800 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h4 className="text-xs font-bold uppercase tracking-wider text-slate-400">Your Local Sovereign Master API Key</h4>
          <code className="text-xs font-mono text-indigo-300 select-all block mt-1">
            agy_live_REDACTED_REVOKED
          </code>
        </div>
        <button
          onClick={() => {
            navigator.clipboard.writeText('agy_live_REDACTED_REVOKED');
            setCopiedKey(true);
            setTimeout(() => setCopiedKey(false), 2000);
          }}
          className="px-4 py-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-xs font-semibold text-slate-200 border border-slate-700 shrink-0 transition"
        >
          {copiedKey ? '✓ Key Copied!' : 'Copy Master Key'}
        </button>
      </div>
    </div>
  );
};
