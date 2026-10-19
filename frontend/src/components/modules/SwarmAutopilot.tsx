import { useState, useEffect } from 'react';
import type { FC } from 'react';
import {
  Play, RefreshCw, Sparkles,
  ArrowRight, ShieldCheck,
  Cpu, Terminal, TrendingUp,
  MessageSquare, Flame, Globe, Camera,
  FileText, Send, CheckCircle2,
  Layers, Search,
  MousePointerClick, Users, Printer, Download
} from 'lucide-react';
import type { TabType } from '../../types';
import { apiFetch, apiErrorMessage } from '../../lib/api';
import { ErrorBanner } from '../shared/ErrorBanner';
import { ExternalLink, CopyablePhone, CopyableEmail } from '../shared/ClickableContact';

interface SwarmAutopilotProps {
  setActiveTab: (t: TabType) => void;
  onBridgeToCopyCoach?: (first: string, company: string, domain: string) => void;
}

interface AutopilotLead {
  lead_id: number;
  company_name: string;
  domain: string;
  contact_name: string;
  resolved_email: string;
  email_confidence: number;
  catch_all_decoded: boolean;
  p_close_percent: number;
  tier: string;
  expected_deal_value_usd: number;
  contract_acv_usd: number;
  monthly_financial_loss_usd: number;
  dispatch_status: string;
  matched_sender: string;
  detected_stack: string[];
  email_preview: {
    subject: string;
    body: string;
  };
}

interface LogEntry {
  timestamp: string;
  agent: string;
  message: string;
  level: string;
}

interface ChatMessage {
  role: 'user' | 'assistant';
  content: string;
  intent?: string;
  suggested_action?: any;
}

const SAMPLE_OBJECTIONS = [
  "We already have an in-house engineering team and don't need agencies.",
  "Your services are too expensive for our current budget cycle.",
  "Bad timing right now, please reach back out next quarter.",
  "What is your pricing model for dedicated pods?"
];

export const SwarmAutopilot: FC<SwarmAutopilotProps> = ({ setActiveTab, onBridgeToCopyCoach }) => {
  // Navigation Sub-modes: 'autopilot' | 'copilot' | 'browser' | 'touch' | 'pods' | 'deck' | 'artifact' | 'diff'
  const [activeMode, setActiveMode] = useState<'autopilot' | 'copilot' | 'browser' | 'touch' | 'pods' | 'deck' | 'artifact' | 'diff'>('autopilot');
  const [error, setError] = useState('');

  // Mode: Human Touch Interactive Browser State
  const [touchUrl, setTouchUrl] = useState('https://news.ycombinator.com');
  const [touchSessionId] = useState('touch_session_main');
  const [touchLoading, setTouchLoading] = useState(false);
  const [touchNavResult, setTouchNavResult] = useState<any>(null);
  const [touchKeystrokes, setTouchKeystrokes] = useState('');
  const [headedStatus, setHeadedStatus] = useState('');
  const [touchLogs, setTouchLogs] = useState<string[]>([]);

  // Mode: Specialized Swarm Pods State
  const [podsDomain, setPodsDomain] = useState('');
  const [podsCompetitor, setPodsCompetitor] = useState('stripe.com');
  const [podsLoading, setPodsLoading] = useState(false);
  const [podsResult, setPodsResult] = useState<any>(null);

  // Mode: Printable Teardown Deck State
  const [deckTarget, setDeckTarget] = useState('');
  const [deckCompetitor, setDeckCompetitor] = useState('stripe.com');
  const [deckVisitors, setDeckVisitors] = useState(50000);
  const [deckAov, setDeckAov] = useState(125);
  const [deckLoading, setDeckLoading] = useState(false);
  const [deckResult, setDeckResult] = useState<any>(null);

  // Mode 5: Competitor Diff Engine State
  const [diffTarget, setDiffTarget] = useState('acmecorp.com');
  const [diffCompetitor, setDiffCompetitor] = useState('stripe.com');
  const [diffLoading, setDiffLoading] = useState(false);
  const [diffResult, setDiffResult] = useState<any>(null);
  const [hookCopied, setHookCopied] = useState(false);

  // Brain Telemetry State
  const [brainStatus, setBrainStatus] = useState<any>(null);
  useEffect(() => {
    apiFetch('/api/brain/status')
      .then(r => r.json())
      .then(d => {
        if (d.status === 'success') setBrainStatus(d.brain);
      })
      .catch(() => {});
  }, []);

  // Mode 1: Swarm Autopilot State
  const [channel, setChannel] = useState('sec_edgar');
  const [query, setQuery] = useState('Form D');
  const [limit, setLimit] = useState(5);
  const [autoEnroll, setAutoEnroll] = useState(true);
  const [running, setRunning] = useState(false);
  const [result, setResult] = useState<any>(null);
  const [leads, setLeads] = useState<AutopilotLead[]>([]);
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [expandedLead, setExpandedLead] = useState<number | null>(null);

  // Inbound Objection Simulator State
  const [objectionText, setObjectionText] = useState(SAMPLE_OBJECTIONS[0]);
  const [simulating, setSimulating] = useState(false);
  const [simulationResult, setSimulationResult] = useState<any>(null);

  // Mode 2: Conversational Swarm Co-Pilot State
  const [chatMessages, setChatMessages] = useState<ChatMessage[]>([
    {
      role: 'assistant',
      content: 'I am your AgencyBD Enterprise Cognitive Brain. I orchestrate autonomous sourcing, native headless Chrome DOM audits, Bayesian P(Close) deal valuations, and cold proposal artifacts. How can I direct the swarm for you today?'
    }
  ]);
  const [chatInput, setChatInput] = useState('');
  const [chatLoading, setChatLoading] = useState(false);
  const [planResult, setPlanResult] = useState<any>(null);

  // Mode 3: Native Headless Browser Studio State
  const [browserDomain, setBrowserDomain] = useState('stripe.com');
  const [browserViewport, setBrowserViewport] = useState<'desktop' | 'mobile'>('desktop');
  const [browserLoading, setBrowserLoading] = useState(false);
  const [browserDomResult, setBrowserDomResult] = useState<any>(null);
  const [browserScreenshotResult, setBrowserScreenshotResult] = useState<any>(null);

  // Mode 4: Proposal Artifact State
  const [artifactLoading, setArtifactLoading] = useState(false);
  const [artifactResult, setArtifactResult] = useState<any>(null);
  const [artifactCopied, setArtifactCopied] = useState(false);

  // Handlers for Mode 1: Swarm Autopilot
  const handleLaunchAutopilot = async () => {
    setRunning(true);
    setError('');
    setResult(null);
    setLeads([]);
    setLogs([
      { timestamp: new Date().toLocaleTimeString(), agent: 'SwarmController', message: 'Initializing autonomous multi-agent pipeline...', level: 'info' }
    ]);

    try {
      const res = await apiFetch('/api/swarm/autopilot/run', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          channel,
          query,
          limit,
          auto_enroll: autoEnroll
        })
      });
      const data = await res.json();
      if (!res.ok) throw new Error(apiErrorMessage(res.status, data));
      
      const payload = data.result || {};
      setResult(payload);
      setLeads(payload.leads || []);
      setLogs(payload.execution_log || []);
      if (payload.leads && payload.leads.length > 0) {
        setExpandedLead(payload.leads[0].lead_id);
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Autonomous Swarm execution failed.');
    } finally {
      setRunning(false);
    }
  };

  const handleSimulateObjection = async () => {
    if (!objectionText.trim()) return;
    setSimulating(true);
    try {
      const res = await apiFetch('/api/brain/triage-objection', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ objection: objectionText, prospect_name: 'Alex', company: 'Target Corp' })
      });
      const data = await res.json();
      if (!res.ok) throw new Error(apiErrorMessage(res.status, data));
      setSimulationResult(data);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Objection simulation failed.');
    } finally {
      setSimulating(false);
    }
  };

  // Handlers for Mode 2: Swarm Co-Pilot
  const handleSendChat = async (textToSend?: string) => {
    const text = (textToSend || chatInput).trim();
    if (!text || chatLoading) return;
    
    const newMessages: ChatMessage[] = [...chatMessages, { role: 'user', content: text }];
    setChatMessages(newMessages);
    setChatInput('');
    setChatLoading(true);

    try {
      const res = await apiFetch('/api/brain/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          messages: newMessages.map(m => ({ role: m.role, content: m.content }))
        })
      });
      const data = await res.json();
      if (!res.ok) throw new Error(apiErrorMessage(res.status, data));

      setChatMessages(prev => [
        ...prev,
        {
          role: 'assistant',
          content: data.reply,
          intent: data.intent,
          suggested_action: data.suggested_action
        }
      ]);

      // If planning intent, trigger ReAct plan preview
      if (data.intent === 'SOURCING_DISPATCH') {
        const planRes = await apiFetch('/api/brain/plan', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ goal: text })
        });
        if (planRes.ok) {
          const planData = await planRes.json();
          setPlanResult(planData);
        }
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Co-pilot interaction failed.');
    } finally {
      setChatLoading(false);
    }
  };

  // Handlers for Mode 3: Native Browser Studio
  const handleRunBrowserAudit = async () => {
    if (!browserDomain.trim() || browserLoading) return;
    setBrowserLoading(true);
    setError('');
    setBrowserDomResult(null);
    setBrowserScreenshotResult(null);

    try {
      // 1. Render virtual DOM
      const domRes = await apiFetch('/api/browser/render', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ domain: browserDomain.trim() })
      });
      const domData = await domRes.json();
      if (!domRes.ok) throw new Error(apiErrorMessage(domRes.status, domData));
      setBrowserDomResult(domData);

      // 2. Capture Screenshot
      const shotRes = await apiFetch('/api/browser/screenshot', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ domain: browserDomain.trim(), viewport: browserViewport })
      });
      const shotData = await shotRes.json();
      if (shotRes.ok) {
        setBrowserScreenshotResult(shotData);
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Native Browser inspection failed.');
    } finally {
      setBrowserLoading(false);
    }
  };

  // Handlers for Mode 4: Proposal Artifact
  const handleGenerateProposalArtifact = async (lead?: AutopilotLead) => {
    setArtifactLoading(true);
    setError('');
    try {
      const res = await apiFetch('/api/brain/artifact', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          lead: lead ? {
            company_name: lead.company_name,
            domain: lead.domain,
            contact_name: lead.contact_name
          } : {
            company_name: "Prospect Enterprise",
            domain: "prospect.com",
            contact_name: "Technical Decision Maker"
          },
          tech_audit: {
            detected_stack: lead?.detected_stack || ["Next.js", "React", "Tailwind CSS"],
            lcp_seconds: 3.6
          },
          deal_metrics: {
            monthly_financial_loss_usd: lead?.monthly_financial_loss_usd || 2700.0,
            expected_value_usd: lead?.expected_deal_value_usd || 58000.0
          }
        })
      });
      const data = await res.json();
      if (!res.ok) throw new Error(apiErrorMessage(res.status, data));
      setArtifactResult(data);
      setActiveMode('artifact');
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Proposal artifact generation failed.');
    } finally {
      setArtifactLoading(false);
    }
  };

  const copyArtifactMarkdown = () => {
    if (artifactResult?.artifact_markdown) {
      navigator.clipboard.writeText(artifactResult.artifact_markdown);
      setArtifactCopied(true);
      setTimeout(() => setArtifactCopied(false), 2000);
    }
  };

  const handleRunDifferential = async () => {
    if (!diffTarget.trim() || !diffCompetitor.trim() || diffLoading) return;
    setDiffLoading(true);
    setError('');
    try {
      const res = await apiFetch('/api/differential/compare', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ target_domain: diffTarget.trim(), competitor_domain: diffCompetitor.trim() })
      });
      const data = await res.json();
      if (!res.ok) throw new Error(apiErrorMessage(res.status, data));
      setDiffResult(data);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Differential comparison failed.');
    } finally {
      setDiffLoading(false);
    }
  };

  // Touch Handlers
  const handleTouchNavigate = async () => {
    if (!touchUrl.trim() || touchLoading) return;
    setTouchLoading(true);
    setError('');
    try {
      const res = await apiFetch('/api/browser/interactive/navigate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ target: touchUrl.trim(), session_id: touchSessionId })
      });
      const data = await res.json();
      if (!res.ok) throw new Error(apiErrorMessage(res.status, data));
      setTouchNavResult(data);
      setTouchLogs(prev => [`[${new Date().toLocaleTimeString()}] Navigated to ${touchUrl}`, ...prev]);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Navigation failed');
    } finally {
      setTouchLoading(false);
    }
  };

  const handleTouchClick = async (e: React.MouseEvent<HTMLImageElement>) => {
    if (!touchNavResult?.viewport_screenshot || touchLoading) return;
    const rect = e.currentTarget.getBoundingClientRect();
    const x = Math.round(((e.clientX - rect.left) / rect.width) * 1280);
    const y = Math.round(((e.clientY - rect.top) / rect.height) * 800);
    setTouchLoading(true);
    try {
      const res = await apiFetch('/api/browser/interactive/action', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          action_type: 'click',
          params: { x, y },
          session_id: touchSessionId
        })
      });
      const data = await res.json();
      if (res.ok) {
        setTouchNavResult((prev: any) => ({ ...prev, viewport_screenshot: data.viewport_screenshot || prev?.viewport_screenshot }));
        setTouchLogs(prev => [`[${new Date().toLocaleTimeString()}] Clicked coordinates (${x}, ${y})`, ...prev]);
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Click action failed');
    } finally {
      setTouchLoading(false);
    }
  };

  const handleTouchType = async () => {
    if (!touchKeystrokes.trim() || touchLoading) return;
    setTouchLoading(true);
    try {
      const res = await apiFetch('/api/browser/interactive/action', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          action_type: 'type',
          params: { text: touchKeystrokes },
          session_id: touchSessionId
        })
      });
      const data = await res.json();
      if (res.ok) {
        setTouchNavResult((prev: any) => ({ ...prev, viewport_screenshot: data.viewport_screenshot || prev?.viewport_screenshot }));
        setTouchLogs(prev => [`[${new Date().toLocaleTimeString()}] Sent keystrokes "${touchKeystrokes}"`, ...prev]);
        setTouchKeystrokes('');
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Type action failed');
    } finally {
      setTouchLoading(false);
    }
  };

  const handleTouchScroll = async (direction: 'up' | 'down') => {
    if (touchLoading) return;
    setTouchLoading(true);
    try {
      const res = await apiFetch('/api/browser/interactive/action', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          action_type: 'scroll',
          params: { direction, amount: 400 },
          session_id: touchSessionId
        })
      });
      const data = await res.json();
      if (res.ok) {
        setTouchNavResult((prev: any) => ({ ...prev, viewport_screenshot: data.viewport_screenshot || prev?.viewport_screenshot }));
        setTouchLogs(prev => [`[${new Date().toLocaleTimeString()}] Scrolled ${direction}`, ...prev]);
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Scroll action failed');
    } finally {
      setTouchLoading(false);
    }
  };

  const handleLaunchHeaded = async () => {
    setHeadedStatus('Launching physical Chrome window on Mac desktop...');
    try {
      const res = await apiFetch('/api/browser/interactive/headed-window', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ url: touchUrl, session_id: touchSessionId })
      });
      const data = await res.json();
      if (res.ok) {
        setHeadedStatus(data.message || 'Headed Chrome launched.');
        setTouchLogs(prev => [`[${new Date().toLocaleTimeString()}] Headed Chrome window opened for manual human takeover`, ...prev]);
      }
    } catch (e) {
      setHeadedStatus(e instanceof Error ? e.message : 'Could not launch headed Chrome');
    }
  };

  // Swarm Pods Handler
  const handleRunPods = async () => {
    setPodsLoading(true);
    setError('');
    try {
      const res = await apiFetch('/api/swarm/pods/run', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          domain: podsDomain.trim(),
          competitor: podsCompetitor.trim(),
          pod_type: 'all'
        })
      });
      const data = await res.json();
      if (!res.ok) throw new Error(apiErrorMessage(res.status, data));
      setPodsResult(data);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Swarm pods execution failed');
    } finally {
      setPodsLoading(false);
    }
  };

  // Teardown Deck Exporter Handler
  const handleExportDeck = async () => {
    setDeckLoading(true);
    setError('');
    try {
      const res = await apiFetch('/api/teardown/deck/export', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          target_domain: deckTarget.trim(),
          competitor_domain: deckCompetitor.trim(),
          monthly_visitors: deckVisitors,
          aov_usd: deckAov,
          output_format: 'both'
        })
      });
      const data = await res.json();
      if (!res.ok) throw new Error(apiErrorMessage(res.status, data));
      setDeckResult(data);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Deck export failed');
    } finally {
      setDeckLoading(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* 1. Header Banner & Cognitive Brain Status */}
      <div className="bg-gradient-to-r from-slate-900 via-indigo-950/60 to-slate-900 border border-indigo-500/30 rounded-2xl p-6 shadow-2xl relative overflow-hidden">
        <div className="absolute top-0 right-0 w-96 h-96 bg-indigo-500/10 rounded-full blur-3xl pointer-events-none" />
        <div className="relative z-10 flex flex-col lg:flex-row lg:items-center justify-between gap-6">
          <div className="space-y-2">
            <div className="flex items-center gap-3">
              <div className="h-10 w-10 rounded-xl bg-gradient-to-tr from-indigo-600 to-purple-600 flex items-center justify-center shadow-lg shadow-indigo-500/30">
                <Cpu className="h-5 w-5 text-white animate-pulse" />
              </div>
              <div>
                <h1 className="text-2xl font-bold tracking-tight text-white flex items-center gap-2">
                  Swarm Auto-Pilot & Cognitive Brain
                  <span className="text-xs px-2.5 py-0.5 rounded-full bg-emerald-500/20 text-emerald-300 border border-emerald-500/30 font-mono font-medium">
                    100% Autonomous
                  </span>
                </h1>
                <p className="text-sm text-slate-400">
                  Self-driving multi-agent BD execution powered by Native Headless Chrome, Bayesian Win Probability (P(Close)), and Cognitive ReAct Reasoning.
                </p>
              </div>
            </div>
          </div>

          {/* Active Brain Telemetry Widget */}
          <div className="flex flex-wrap items-center gap-3 bg-slate-950/70 border border-slate-800 rounded-xl p-3 shadow-inner">
            <div className="flex items-center gap-2 pr-3 border-r border-slate-800">
              <span className="h-2.5 w-2.5 rounded-full bg-emerald-400 animate-ping" />
              <div className="text-xs">
                <div className="text-slate-400 font-mono">Cognitive Brain</div>
                <div className="text-indigo-300 font-semibold flex items-center gap-1">
                  {brainStatus?.provider || 'Native Heuristic Brain'}
                </div>
              </div>
            </div>

            <div className="flex items-center gap-2 pr-3 border-r border-slate-800">
              <Globe className="h-4 w-4 text-cyan-400" />
              <div className="text-xs">
                <div className="text-slate-400 font-mono">Browser Engine</div>
                <div className="text-cyan-300 font-semibold">Headless Chromium</div>
              </div>
            </div>

            <div className="flex items-center gap-2">
              <ShieldCheck className="h-4 w-4 text-emerald-400" />
              <div className="text-xs">
                <div className="text-slate-400 font-mono">API Operating Cost</div>
                <div className="text-emerald-300 font-semibold">$0.00 (Sovereign)</div>
              </div>
            </div>
          </div>
        </div>

        {/* 2. Sub-Navigation Tabs */}
        <div className="flex items-center gap-2 mt-6 pt-4 border-t border-slate-800/80 overflow-x-auto">
          <button
            onClick={() => setActiveMode('autopilot')}
            className={`px-4 py-2 rounded-lg text-sm font-medium transition-all flex items-center gap-2 ${
              activeMode === 'autopilot'
                ? 'bg-indigo-600 text-white shadow-lg shadow-indigo-600/30'
                : 'text-slate-400 hover:text-white hover:bg-slate-800/60'
            }`}
          >
            <Play className="h-4 w-4" />
            Auto-Pilot Loop
          </button>

          <button
            onClick={() => setActiveMode('pods')}
            className={`px-4 py-2 rounded-lg text-sm font-medium transition-all flex items-center gap-2 ${
              activeMode === 'pods'
                ? 'bg-indigo-600 text-white shadow-lg shadow-indigo-600/30'
                : 'text-slate-400 hover:text-white hover:bg-slate-800/60'
            }`}
          >
            <Users className="h-4 w-4" />
            Swarm Pods (5 Specialists)
          </button>

          <button
            onClick={() => setActiveMode('touch')}
            className={`px-4 py-2 rounded-lg text-sm font-medium transition-all flex items-center gap-2 ${
              activeMode === 'touch'
                ? 'bg-indigo-600 text-white shadow-lg shadow-indigo-600/30'
                : 'text-slate-400 hover:text-white hover:bg-slate-800/60'
            }`}
          >
            <MousePointerClick className="h-4 w-4" />
            Human Touch Browser
          </button>

          <button
            onClick={() => setActiveMode('deck')}
            className={`px-4 py-2 rounded-lg text-sm font-medium transition-all flex items-center gap-2 ${
              activeMode === 'deck'
                ? 'bg-indigo-600 text-white shadow-lg shadow-indigo-600/30'
                : 'text-slate-400 hover:text-white hover:bg-slate-800/60'
            }`}
          >
            <Printer className="h-4 w-4" />
            Executive Teardown Deck
          </button>

          <button
            onClick={() => setActiveMode('copilot')}
            className={`px-4 py-2 rounded-lg text-sm font-medium transition-all flex items-center gap-2 ${
              activeMode === 'copilot'
                ? 'bg-indigo-600 text-white shadow-lg shadow-indigo-600/30'
                : 'text-slate-400 hover:text-white hover:bg-slate-800/60'
            }`}
          >
            <MessageSquare className="h-4 w-4" />
            Swarm Co-Pilot (Claude-Brain)
          </button>

          <button
            onClick={() => setActiveMode('browser')}
            className={`px-4 py-2 rounded-lg text-sm font-medium transition-all flex items-center gap-2 ${
              activeMode === 'browser'
                ? 'bg-indigo-600 text-white shadow-lg shadow-indigo-600/30'
                : 'text-slate-400 hover:text-white hover:bg-slate-800/60'
            }`}
          >
            <Camera className="h-4 w-4" />
            Native Headless Browser Studio
          </button>

          <button
            onClick={() => {
              if (!artifactResult) handleGenerateProposalArtifact();
              else setActiveMode('artifact');
            }}
            className={`px-4 py-2 rounded-lg text-sm font-medium transition-all flex items-center gap-2 ${
              activeMode === 'artifact'
                ? 'bg-indigo-600 text-white shadow-lg shadow-indigo-600/30'
                : 'text-slate-400 hover:text-white hover:bg-slate-800/60'
            }`}
          >
            <FileText className="h-4 w-4" />
            Proposal Artifacts
          </button>

          <button
            onClick={() => setActiveMode('diff')}
            className={`px-4 py-2 rounded-lg text-sm font-medium transition-all flex items-center gap-2 ${
              activeMode === 'diff'
                ? 'bg-indigo-600 text-white shadow-lg shadow-indigo-600/30'
                : 'text-slate-400 hover:text-white hover:bg-slate-800/60'
            }`}
          >
            <TrendingUp className="h-4 w-4" />
            Competitor Diff Engine
          </button>
        </div>
      </div>

      <ErrorBanner message={error} />

      {/* =========================================================================
          MODE 1: AUTOPILOT LOOP & VALUATION GRID
         ========================================================================= */}
      {activeMode === 'autopilot' && (
        <div className="space-y-6">
          {/* Mission Control Trigger Bar */}
          <div className="bg-slate-900/80 border border-slate-800 rounded-xl p-5 shadow-xl flex flex-wrap items-center justify-between gap-4">
            <div className="flex flex-wrap items-center gap-4">
              <div>
                <label className="text-xs text-slate-400 font-mono block mb-1">Target Venture Channel</label>
                <select
                  value={channel}
                  onChange={(e) => setChannel(e.target.value)}
                  className="bg-slate-950 border border-slate-800 text-white text-sm rounded-lg px-3 py-2 outline-none focus:border-indigo-500 font-mono"
                >
                  <option value="sec_edgar">SEC EDGAR Form D (Venture Capital & IPOs)</option>
                  <option value="open_directories">Open Sovereign Business Registries</option>
                </select>
              </div>

              <div>
                <label className="text-xs text-slate-400 font-mono block mb-1">Keywords</label>
                <input
                  type="text"
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                  className="w-28 bg-slate-950 border border-slate-800 text-white text-sm rounded-lg px-3 py-2 outline-none focus:border-indigo-500 font-mono"
                />
              </div>

              <div>
                <label className="text-xs text-slate-400 font-mono block mb-1">Batch Limit</label>
                <input
                  type="number"
                  min="1"
                  max="20"
                  value={limit}
                  onChange={(e) => setLimit(Math.max(1, parseInt(e.target.value) || 1))}
                  className="w-20 bg-slate-950 border border-slate-800 text-white text-sm rounded-lg px-3 py-2 outline-none focus:border-indigo-500 font-mono"
                />
              </div>

              <div className="flex items-center gap-2 pt-5">
                <input
                  type="checkbox"
                  id="autoEnroll"
                  checked={autoEnroll}
                  onChange={(e) => setAutoEnroll(e.target.checked)}
                  className="rounded border-slate-700 bg-slate-950 text-indigo-600 focus:ring-indigo-500 h-4 w-4 cursor-pointer"
                />
                <label htmlFor="autoEnroll" className="text-xs text-slate-300 cursor-pointer select-none">
                  Auto-Enroll Tier 1 Leads into Smartlead Cadence
                </label>
              </div>
            </div>

            <button
              onClick={handleLaunchAutopilot}
              disabled={running}
              className={`px-5 py-2.5 rounded-lg text-sm font-semibold flex items-center gap-2 text-white shadow-lg transition-all ${
                running
                  ? 'bg-indigo-500/50 cursor-not-allowed'
                  : 'bg-gradient-to-r from-indigo-600 to-purple-600 hover:from-indigo-500 hover:to-purple-500 shadow-indigo-600/30'
              }`}
            >
              {running ? (
                <>
                  <RefreshCw className="h-4 w-4 animate-spin" />
                  Running Swarm Autopilot...
                </>
              ) : (
                <>
                  <Play className="h-4 w-4 fill-white" />
                  Launch Sovereign BD Cycle
                </>
              )}
            </button>
          </div>

          {/* Mathematical Valuation Cards */}
          {result && (
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
              <div className="bg-slate-900/90 border border-slate-800 rounded-xl p-4 shadow-lg">
                <div className="text-xs text-slate-400 font-mono">Leads Sourced & Evaluated</div>
                <div className="text-2xl font-bold text-white mt-1">{result.leads_processed} Accounts</div>
                <div className="text-xs text-indigo-400 mt-1 flex items-center gap-1 font-mono">
                  <CheckCircle2 className="h-3.5 w-3.5" /> 100% Keyless Verification
                </div>
              </div>

              <div className="bg-slate-900/90 border border-slate-800 rounded-xl p-4 shadow-lg">
                <div className="text-xs text-slate-400 font-mono">Auto-Enrolled to Cadence</div>
                <div className="text-2xl font-bold text-emerald-400 mt-1">{result.leads_auto_enrolled} Leads</div>
                <div className="text-xs text-slate-400 mt-1 font-mono">Smartlead ESP Matched</div>
              </div>

              <div className="bg-slate-900/90 border border-slate-800 rounded-xl p-4 shadow-lg">
                <div className="text-xs text-slate-400 font-mono">Total Pipeline Valuation E[Deal]</div>
                <div className="text-2xl font-bold text-purple-400 mt-1">
                  ${(result.total_expected_pipeline_usd || 0).toLocaleString('en-US', { minimumFractionDigits: 2 })}
                </div>
                <div className="text-xs text-slate-400 mt-1 font-mono">Bayesian Probability Weighted</div>
              </div>

              <div className="bg-slate-900/90 border border-slate-800 rounded-xl p-4 shadow-lg">
                <div className="text-xs text-slate-400 font-mono">Monthly Client Delay Cost</div>
                <div className="text-2xl font-bold text-rose-400 mt-1">
                  ${(result.total_monthly_financial_loss_usd || 0).toLocaleString('en-US', { minimumFractionDigits: 2 })}/mo
                </div>
                <div className="text-xs text-slate-400 mt-1 font-mono">Quantitative Outreach Hook</div>
              </div>
            </div>
          )}

          {/* Autopilot Execution Terminal Log */}
          {logs.length > 0 && (
            <div className="bg-slate-950 border border-slate-800 rounded-xl p-4 shadow-2xl font-mono text-xs">
              <div className="flex items-center justify-between pb-3 border-b border-slate-800 mb-3 text-slate-400">
                <span className="flex items-center gap-2">
                  <Terminal className="h-4 w-4 text-indigo-400" />
                  Autonomous Swarm Live Audit Trail
                </span>
                <span className="text-slate-500">{logs.length} operations</span>
              </div>
              <div className="space-y-1.5 max-h-56 overflow-y-auto pr-2">
                {logs.map((log, idx) => (
                  <div key={idx} className="flex items-start gap-2">
                    <span className="text-slate-600 shrink-0">{log.timestamp}</span>
                    <span className="text-indigo-400 font-semibold shrink-0">[{log.agent}]</span>
                    <span className={
                      log.level === 'success' ? 'text-emerald-400' :
                      log.level === 'warn' ? 'text-amber-400' :
                      log.level === 'error' ? 'text-rose-400' : 'text-slate-300'
                    }>
                      {log.message}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Sourced Leads Grid */}
          {leads.length > 0 && (
            <div className="space-y-4">
              <h2 className="text-lg font-bold text-white flex items-center gap-2">
                <TrendingUp className="h-5 w-5 text-indigo-400" />
                Bayesian Scored High-Value Prospects
              </h2>
              <div className="space-y-3">
                {leads.map((lead) => {
                  const isExpanded = expandedLead === lead.lead_id;
                  return (
                    <div
                      key={lead.lead_id}
                      className="bg-slate-900/80 border border-slate-800 hover:border-slate-700 rounded-xl p-4 transition-all"
                    >
                      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
                        <div className="space-y-1">
                          <div className="flex items-center gap-2">
                            <span className="text-white font-bold text-base">{lead.company_name}</span>
                            <ExternalLink href={lead.domain} className="text-xs font-mono" />
                            <span className="px-2 py-0.5 rounded text-xs font-mono font-semibold bg-indigo-500/20 text-indigo-300 border border-indigo-500/30">
                              {lead.tier}
                            </span>
                          </div>
                          <div className="text-xs text-slate-400 flex flex-wrap items-center gap-3">
                            <span>Contact: <strong className="text-slate-200">{lead.contact_name}</strong></span>
                            <span>•</span>
                            <div className="flex items-center gap-1.5">
                              <CopyableEmail email={lead.resolved_email} />
                              <span className="text-[10px] font-mono text-emerald-400">({lead.email_confidence}% Conf)</span>
                            </div>
                          </div>
                        </div>

                        <div className="flex items-center gap-6">
                          <div className="text-right">
                            <div className="text-xs text-slate-400 font-mono">Win Probability P(Close)</div>
                            <div className="text-lg font-bold text-emerald-400 font-mono">{lead.p_close_percent}%</div>
                          </div>

                          <div className="text-right">
                            <div className="text-xs text-slate-400 font-mono">Expected Deal E[Deal]</div>
                            <div className="text-lg font-bold text-purple-400 font-mono">
                              ${lead.expected_deal_value_usd.toLocaleString('en-US', { minimumFractionDigits: 0 })}
                            </div>
                          </div>

                          <button
                            onClick={() => setExpandedLead(isExpanded ? null : lead.lead_id)}
                            className="px-3 py-1.5 rounded-lg text-xs font-medium bg-slate-800 hover:bg-slate-700 text-slate-300 transition-colors"
                          >
                            {isExpanded ? 'Hide Teardown' : 'View Teardown'}
                          </button>
                        </div>
                      </div>

                      {/* Expanded Lead Details */}
                      {isExpanded && (
                        <div className="mt-4 pt-4 border-t border-slate-800 space-y-4">
                          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                            <div className="bg-slate-950 p-3.5 rounded-lg border border-slate-800/80">
                              <div className="text-xs font-bold text-indigo-300 uppercase tracking-wider mb-2 font-mono flex items-center justify-between">
                                <span>Personalized Technical Sequence</span>
                                <span className="text-slate-500">Sender: {lead.matched_sender}</span>
                              </div>
                              <div className="text-xs text-slate-400 mb-1">
                                <strong>Subject:</strong> {lead.email_preview.subject}
                              </div>
                              <div className="text-xs text-slate-300 whitespace-pre-line bg-slate-900/50 p-2.5 rounded border border-slate-800/50 font-sans">
                                {lead.email_preview.body}
                              </div>
                            </div>

                            <div className="bg-slate-950 p-3.5 rounded-lg border border-slate-800/80 flex flex-col justify-between">
                              <div>
                                <div className="text-xs font-bold text-purple-300 uppercase tracking-wider mb-2 font-mono">
                                  Prospect Diagnostic Profile
                                </div>
                                <div className="space-y-1.5 text-xs text-slate-300">
                                  <div>Target ACV: <strong className="text-white">${lead.contract_acv_usd.toLocaleString()}</strong></div>
                                  <div>Monthly Delay Hemorrhage: <strong className="text-rose-400">${lead.monthly_financial_loss_usd.toLocaleString()}/mo</strong></div>
                                  <div>Detected Stack: {lead.detected_stack.join(', ') || 'Modern Web App'}</div>
                                  <div>Dispatch Status: <span className="text-emerald-400 font-mono">{lead.dispatch_status}</span></div>
                                </div>
                              </div>

                              <div className="flex items-center gap-2 mt-4 pt-3 border-t border-slate-800">
                                <button
                                  onClick={() => handleGenerateProposalArtifact(lead)}
                                  className="px-3 py-1.5 rounded-lg text-xs font-semibold bg-indigo-600 hover:bg-indigo-500 text-white flex items-center gap-1.5 transition-colors"
                                >
                                  <FileText className="h-3.5 w-3.5" />
                                  View Full Proposal Artifact
                                </button>
                                <button
                                  onClick={() => setActiveTab('doctor')}
                                  className="px-3 py-1.5 rounded-lg text-xs font-semibold bg-slate-800 hover:bg-slate-700 text-slate-300 flex items-center gap-1.5 transition-colors"
                                >
                                  Open in Website Doctor
                                </button>
                                {onBridgeToCopyCoach && (
                                  <button
                                    onClick={() => onBridgeToCopyCoach(lead.contact_name.split(' ')[0], lead.company_name, lead.domain)}
                                    className="px-3 py-1.5 rounded-lg text-xs font-semibold bg-slate-800 hover:bg-slate-700 text-slate-300 flex items-center gap-1.5 transition-colors"
                                  >
                                    Bridge to Copy Coach <ArrowRight className="h-3.5 w-3.5" />
                                  </button>
                                )}
                              </div>
                            </div>
                          </div>
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {/* Inbound Objection Triage Simulator */}
          <div className="bg-slate-900/80 border border-slate-800 rounded-xl p-5 shadow-xl space-y-4">
            <div className="flex items-center justify-between">
              <div>
                <h3 className="text-base font-bold text-white flex items-center gap-2">
                  <Flame className="h-4 w-4 text-amber-400" />
                  Inbound Objection Triage Simulator
                </h3>
                <p className="text-xs text-slate-400">
                  Simulate live prospect objections. The Cognitive Brain classifies category and constructs mathematically framed rebuttals.
                </p>
              </div>
            </div>

            <div className="flex flex-col sm:flex-row items-center gap-3">
              <select
                value={objectionText}
                onChange={(e) => setObjectionText(e.target.value)}
                className="w-full sm:flex-1 bg-slate-950 border border-slate-800 text-white text-xs rounded-lg px-3 py-2.5 outline-none focus:border-indigo-500"
              >
                {SAMPLE_OBJECTIONS.map((obj, i) => (
                  <option key={i} value={obj}>{obj}</option>
                ))}
              </select>

              <button
                onClick={handleSimulateObjection}
                disabled={simulating}
                className="w-full sm:w-auto px-4 py-2.5 rounded-lg text-xs font-semibold bg-amber-600 hover:bg-amber-500 text-white flex items-center justify-center gap-2 transition-colors shrink-0 shadow-lg shadow-amber-600/20"
              >
                {simulating ? <RefreshCw className="h-3.5 w-3.5 animate-spin" /> : <Sparkles className="h-3.5 w-3.5" />}
                Generate Rebuttal
              </button>
            </div>

            {simulationResult && (
              <div className="bg-slate-950 p-4 rounded-xl border border-slate-800 space-y-2 text-xs">
                <div className="flex items-center justify-between border-b border-slate-800/80 pb-2">
                  <span className="text-slate-400 font-mono">Category: <strong className="text-amber-300">{simulationResult.category}</strong></span>
                  <span className="text-slate-400 font-mono">Angle: <strong className="text-indigo-300">{simulationResult.rebuttal_strategy}</strong></span>
                </div>
                <div className="text-slate-300 whitespace-pre-line bg-slate-900/60 p-3 rounded-lg border border-slate-800/50 font-sans">
                  {simulationResult.draft_reply}
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {/* =========================================================================
          MODE 2: SWARM CO-PILOT (CLAUDE-BRAIN REASONING)
         ========================================================================= */}
      {activeMode === 'copilot' && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          <div className="lg:col-span-2 space-y-4">
            <div className="bg-slate-900/80 border border-slate-800 rounded-xl p-5 shadow-xl flex flex-col h-[540px]">
              <div className="flex items-center justify-between pb-3 border-b border-slate-800 mb-3">
                <div className="flex items-center gap-2">
                  <MessageSquare className="h-4 w-4 text-indigo-400" />
                  <span className="text-sm font-bold text-white">Conversational Swarm Co-Pilot</span>
                </div>
                <span className="text-xs text-indigo-300 font-mono bg-indigo-500/10 border border-indigo-500/20 px-2 py-0.5 rounded">
                  ReAct Reasoning
                </span>
              </div>

              {/* Chat Messages Log */}
              <div className="flex-1 overflow-y-auto space-y-3 pr-2 text-xs">
                {chatMessages.map((msg, i) => (
                  <div
                    key={i}
                    className={`flex flex-col ${msg.role === 'user' ? 'items-end' : 'items-start'}`}
                  >
                    <div
                      className={`max-w-[85%] rounded-xl p-3.5 shadow-md ${
                        msg.role === 'user'
                          ? 'bg-indigo-600 text-white'
                          : 'bg-slate-950 text-slate-200 border border-slate-800 whitespace-pre-line'
                      }`}
                    >
                      {msg.content}
                    </div>
                  </div>
                ))}
                {chatLoading && (
                  <div className="flex items-center gap-2 text-slate-400 text-xs font-mono p-2">
                    <RefreshCw className="h-3.5 w-3.5 animate-spin text-indigo-400" />
                    Cognitive Brain is thinking and formulating plan...
                  </div>
                )}
              </div>

              {/* Quick Prompt Suggestions */}
              <div className="pt-3 border-t border-slate-800/80 flex flex-wrap gap-1.5 mb-3">
                <button
                  onClick={() => handleSendChat("Find 5 Series A AI startups in California with slow mobile sites")}
                  className="px-2.5 py-1 rounded bg-slate-800/80 hover:bg-slate-700 text-slate-300 text-[11px] transition-colors"
                >
                  ⚡ Find 5 Series A AI startups
                </button>
                <button
                  onClick={() => handleSendChat("Audit stripe.com with headless browser")}
                  className="px-2.5 py-1 rounded bg-slate-800/80 hover:bg-slate-700 text-slate-300 text-[11px] transition-colors"
                >
                  ⚡ Headless audit stripe.com
                </button>
                <button
                  onClick={() => handleSendChat("Rebut objection: we already have an internal engineering team")}
                  className="px-2.5 py-1 rounded bg-slate-800/80 hover:bg-slate-700 text-slate-300 text-[11px] transition-colors"
                >
                  ⚡ In-house team rebuttal
                </button>
              </div>

              {/* Chat Input */}
              <div className="flex items-center gap-2">
                <input
                  type="text"
                  placeholder="Give a command to your swarm (e.g. 'Source 10 fintechs funded this month and audit tech stack')..."
                  value={chatInput}
                  onChange={(e) => setChatInput(e.target.value)}
                  onKeyDown={(e) => e.key === 'Enter' && handleSendChat()}
                  className="flex-1 bg-slate-950 border border-slate-800 text-white text-xs rounded-lg px-3 py-2.5 outline-none focus:border-indigo-500"
                />
                <button
                  onClick={() => handleSendChat()}
                  disabled={chatLoading}
                  className="px-4 py-2.5 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white font-semibold text-xs flex items-center gap-1.5 transition-colors shadow-lg shadow-indigo-600/30"
                >
                  <Send className="h-3.5 w-3.5" />
                  Send
                </button>
              </div>
            </div>
          </div>

          {/* Right Rail: ReAct Planning Breakdown */}
          <div className="space-y-4">
            <div className="bg-slate-900/80 border border-slate-800 rounded-xl p-5 shadow-xl space-y-3">
              <h3 className="text-sm font-bold text-white flex items-center gap-2">
                <Terminal className="h-4 w-4 text-purple-400" />
                Claude-Style ReAct Execution Plan
              </h3>
              <p className="text-xs text-slate-400">
                Systematic decomposition of target goal into automated multi-agent phases with verification checkpoints.
              </p>

              {planResult ? (
                <div className="space-y-2 mt-3">
                  {planResult.execution_plan.map((step: any, idx: number) => (
                    <div key={idx} className="bg-slate-950 p-2.5 rounded border border-slate-800 text-xs">
                      <div className="flex items-center justify-between text-indigo-300 font-mono font-bold mb-1">
                        <span>Phase {step.step}: {step.phase}</span>
                      </div>
                      <div className="text-slate-300 text-[11px] mb-1">{step.thought}</div>
                      <div className="text-slate-500 font-mono text-[10px]">Action: {step.action}</div>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="p-6 text-center text-slate-500 text-xs border border-dashed border-slate-800 rounded-lg">
                  Submit a sourcing or audit command in the Co-Pilot to generate a ReAct multi-phase plan.
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* =========================================================================
          MODE 3: NATIVE HEADLESS BROWSER STUDIO
         ========================================================================= */}
      {activeMode === 'browser' && (
        <div className="space-y-6">
          <div className="bg-slate-900/80 border border-slate-800 rounded-xl p-5 shadow-xl space-y-4">
            <div>
              <h2 className="text-base font-bold text-white flex items-center gap-2">
                <Camera className="h-4 w-4 text-cyan-400" />
                Headless Chromium Virtual DOM & Screenshot Studio
              </h2>
              <p className="text-xs text-slate-400">
                Renders modern client-side Single Page Apps (React, Next.js, Vue) via headless Chromium to unearth hidden contact details and capture proof screenshots.
              </p>
            </div>

            <div className="flex flex-col sm:flex-row items-center gap-3">
              <div className="flex-1 w-full">
                <input
                  type="text"
                  placeholder="Enter domain to audit (e.g. vercel.com, shopify.com)..."
                  value={browserDomain}
                  onChange={(e) => setBrowserDomain(e.target.value)}
                  className="w-full bg-slate-950 border border-slate-800 text-white text-xs rounded-lg px-3 py-2.5 outline-none focus:border-cyan-500 font-mono"
                />
              </div>

              <div className="flex items-center gap-2 w-full sm:w-auto">
                <select
                  value={browserViewport}
                  onChange={(e) => setBrowserViewport(e.target.value as any)}
                  className="bg-slate-950 border border-slate-800 text-white text-xs rounded-lg px-3 py-2.5 outline-none focus:border-cyan-500 font-mono"
                >
                  <option value="desktop">Desktop (1440x900)</option>
                  <option value="mobile">Mobile Viewport (375x812)</option>
                </select>

                <button
                  onClick={handleRunBrowserAudit}
                  disabled={browserLoading}
                  className="px-5 py-2.5 rounded-lg text-xs font-semibold bg-cyan-600 hover:bg-cyan-500 text-white flex items-center gap-2 transition-colors shrink-0 shadow-lg shadow-cyan-600/20"
                >
                  {browserLoading ? (
                    <>
                      <RefreshCw className="h-3.5 w-3.5 animate-spin" />
                      Rendering Chromium...
                    </>
                  ) : (
                    <>
                      <Search className="h-3.5 w-3.5" />
                      Render & Inspect
                    </>
                  )}
                </button>
              </div>
            </div>
          </div>

          {/* Browser Inspection Results Split Screen */}
          {(browserDomResult || browserScreenshotResult) && (
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              {/* Left Panel: Virtual DOM Intelligence */}
              <div className="bg-slate-900/80 border border-slate-800 rounded-xl p-5 shadow-xl space-y-4">
                <h3 className="text-sm font-bold text-white flex items-center justify-between border-b border-slate-800 pb-2">
                  <span>Virtual DOM Intelligence</span>
                  <span className="text-xs font-mono text-cyan-400">Rendered via {browserDomResult?.rendered_by}</span>
                </h3>

                {browserDomResult && (
                  <div className="space-y-3 text-xs">
                    <div>
                      <span className="text-slate-400 font-mono block">Page Title</span>
                      <span className="text-white font-medium">{browserDomResult.title || 'N/A'}</span>
                    </div>

                    <div>
                      <span className="text-slate-400 font-mono block">Detected Tech Stack</span>
                      <div className="flex flex-wrap gap-1.5 mt-1">
                        {browserDomResult.detected_stack?.length > 0 ? (
                          browserDomResult.detected_stack.map((t: string, i: number) => (
                            <span key={i} className="px-2 py-0.5 rounded bg-indigo-500/20 text-indigo-300 border border-indigo-500/30 text-[11px] font-mono">
                              {t}
                            </span>
                          ))
                        ) : (
                          <span className="text-slate-500">No major framework signatures detected</span>
                        )}
                      </div>
                    </div>

                    <div>
                      <span className="text-slate-400 font-mono block">Discovered Email Inboxes</span>
                      <div className="space-y-1 mt-1">
                        {browserDomResult.emails?.length > 0 ? (
                          browserDomResult.emails.map((em: string, i: number) => (
                            <div key={i} className="text-emerald-400 font-mono">{em}</div>
                          ))
                        ) : (
                          <span className="text-slate-500">No public mailto or regex emails in DOM</span>
                        )}
                      </div>
                    </div>

                    <div>
                      <span className="text-slate-400 font-mono block">Social / LinkedIn Links</span>
                      <div className="space-y-1 mt-1">
                        {browserDomResult.linkedin_urls?.length > 0 ? (
                          browserDomResult.linkedin_urls.map((u: string, i: number) => (
                            <a key={i} href={u} target="_blank" rel="noreferrer" className="text-cyan-400 hover:underline font-mono flex items-center gap-1">
                              {u} <ExternalLink className="h-3 w-3" />
                            </a>
                          ))
                        ) : (
                          <span className="text-slate-500">None detected</span>
                        )}
                      </div>
                    </div>
                  </div>
                )}
              </div>

              {/* Right Panel: High-Res Screenshot Teardown */}
              <div className="bg-slate-900/80 border border-slate-800 rounded-xl p-5 shadow-xl space-y-4">
                <h3 className="text-sm font-bold text-white flex items-center justify-between border-b border-slate-800 pb-2">
                  <span>Visual Teardown Screenshot</span>
                  <span className="text-xs font-mono text-slate-400">{browserViewport} mode</span>
                </h3>

                {browserScreenshotResult?.data_uri ? (
                  <div className="bg-slate-950 rounded-lg p-2 border border-slate-800 text-center overflow-hidden">
                    <img
                      src={browserScreenshotResult.data_uri}
                      alt="Website screenshot"
                      className="rounded border border-slate-800 max-h-[420px] mx-auto object-contain shadow-2xl"
                    />
                    <div className="text-[11px] text-slate-500 font-mono mt-2">
                      Captured live via Chromium ({browserScreenshotResult.file_size_bytes} bytes)
                    </div>
                  </div>
                ) : (
                  <div className="p-12 text-center text-slate-500 text-xs border border-dashed border-slate-800 rounded-lg">
                    Screenshot will render here after clicking 'Render & Inspect'.
                  </div>
                )}
              </div>
            </div>
          )}
        </div>
      )}

      {/* =========================================================================
          MODE 4: PROPOSAL ARTIFACT VIEWER
         ========================================================================= */}
      {activeMode === 'artifact' && (
        <div className="space-y-4">
          <div className="bg-slate-900/80 border border-slate-800 rounded-xl p-5 shadow-xl flex items-center justify-between gap-4">
            <div>
              <h2 className="text-base font-bold text-white flex items-center gap-2">
                <FileText className="h-4 w-4 text-indigo-400" />
                Claude-Style Proposal & Technical Teardown Artifact
              </h2>
              <p className="text-xs text-slate-400">
                KaTeX-rendered mathematical revenue loss proof and 30-day engineering sprint roadmap ready to share with clients.
              </p>
            </div>

            <div className="flex items-center gap-2">
              <button
                onClick={copyArtifactMarkdown}
                className="px-4 py-2 rounded-lg text-xs font-semibold bg-slate-800 hover:bg-slate-700 text-white flex items-center gap-1.5 transition-colors"
              >
                {artifactCopied ? <CheckCircle2 className="h-3.5 w-3.5 text-emerald-400" /> : <Layers className="h-3.5 w-3.5" />}
                {artifactCopied ? 'Copied Markdown!' : 'Copy Markdown'}
              </button>

              <button
                onClick={() => handleGenerateProposalArtifact()}
                disabled={artifactLoading}
                className="px-4 py-2 rounded-lg text-xs font-semibold bg-indigo-600 hover:bg-indigo-500 text-white flex items-center gap-1.5 transition-colors shadow-lg shadow-indigo-600/30"
              >
                <RefreshCw className={`h-3.5 w-3.5 ${artifactLoading ? 'animate-spin' : ''}`} />
                Regenerate Artifact
              </button>
            </div>
          </div>

          {artifactResult && (
            <div className="bg-slate-950 border border-slate-800 rounded-xl p-6 shadow-2xl space-y-4">
              <div className="flex items-center justify-between border-b border-slate-800 pb-3">
                <span className="text-sm font-bold text-white">{artifactResult.artifact_title}</span>
                <span className="text-xs font-mono text-emerald-400">
                  Valuation: ${(artifactResult.metrics?.expected_deal_usd || 0).toLocaleString()} USD
                </span>
              </div>

              <div className="prose prose-invert max-w-none text-xs text-slate-300 font-mono whitespace-pre-wrap leading-relaxed bg-slate-900/60 p-5 rounded-xl border border-slate-800/80">
                {artifactResult.artifact_markdown}
              </div>
            </div>
          )}
        </div>
      )}

      {/* =========================================================================
          MODE 5: COMPETITOR DIFFERENTIAL ENGINE (REA PATTERN)
         ========================================================================= */}
      {activeMode === 'diff' && (
        <div className="space-y-6">
          <div className="bg-slate-900/80 border border-slate-800 rounded-xl p-5 shadow-xl space-y-4">
            <div>
              <h2 className="text-base font-bold text-white flex items-center gap-2">
                <TrendingUp className="h-4 w-4 text-purple-400" />
                Semantic Differential Comparison: Target vs. Benchmark
              </h2>
              <p className="text-xs text-slate-400">
                Pits your prospect's DOM and Core Web Vitals against their #1 competitor to generate mathematically unassailable cold outreach hooks.
              </p>
            </div>

            <div className="flex flex-col sm:flex-row items-center gap-3">
              <div className="flex-1 w-full">
                <label className="text-xs text-slate-400 font-mono block mb-1">Target Prospect Domain</label>
                <input
                  type="text"
                  placeholder="e.g. acmecorp.com"
                  value={diffTarget}
                  onChange={(e) => setDiffTarget(e.target.value)}
                  className="w-full bg-slate-950 border border-slate-800 text-white text-xs rounded-lg px-3 py-2.5 outline-none focus:border-indigo-500 font-mono"
                />
              </div>

              <div className="flex-1 w-full">
                <label className="text-xs text-slate-400 font-mono block mb-1">Key Competitor / Industry Leader</label>
                <input
                  type="text"
                  placeholder="e.g. stripe.com"
                  value={diffCompetitor}
                  onChange={(e) => setDiffCompetitor(e.target.value)}
                  className="w-full bg-slate-950 border border-slate-800 text-white text-xs rounded-lg px-3 py-2.5 outline-none focus:border-purple-500 font-mono"
                />
              </div>

              <div className="pt-5 w-full sm:w-auto">
                <button
                  onClick={handleRunDifferential}
                  disabled={diffLoading}
                  className="w-full sm:w-auto px-5 py-2.5 rounded-lg text-xs font-semibold bg-gradient-to-r from-purple-600 to-indigo-600 hover:from-purple-500 hover:to-indigo-500 text-white flex items-center justify-center gap-2 transition-colors shadow-lg shadow-purple-600/20"
                >
                  {diffLoading ? <RefreshCw className="h-3.5 w-3.5 animate-spin" /> : <Layers className="h-3.5 w-3.5" />}
                  Generate Teardown Diff
                </button>
              </div>
            </div>
          </div>

          {diffResult && (
            <div className="space-y-4">
              {/* Pitch Hook Callout */}
              <div className="bg-gradient-to-r from-purple-950/40 via-indigo-950/40 to-slate-950 border border-purple-500/30 rounded-xl p-5 shadow-xl space-y-3">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-mono font-bold text-purple-300 uppercase tracking-wider">
                    High-Converting Comparative Outreach Hook
                  </span>
                  <button
                    onClick={() => {
                      navigator.clipboard.writeText(diffResult.differential?.competitive_pitch_hook || '');
                      setHookCopied(true);
                      setTimeout(() => setHookCopied(false), 2000);
                    }}
                    className="px-3 py-1.5 rounded-lg text-xs font-semibold bg-slate-800 hover:bg-slate-700 text-slate-300 flex items-center gap-1.5 transition-colors"
                  >
                    {hookCopied ? <CheckCircle2 className="h-3.5 w-3.5 text-emerald-400" /> : <Layers className="h-3.5 w-3.5" />}
                    {hookCopied ? 'Copied Hook!' : 'Copy Hook'}
                  </button>
                </div>
                <div className="text-sm font-sans text-white p-3.5 bg-slate-900/60 rounded-lg border border-slate-800/80 leading-relaxed">
                  "{diffResult.differential?.competitive_pitch_hook}"
                </div>
              </div>

              {/* Side-by-Side Diagnostic Cards */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {/* Target Card */}
                <div className="bg-slate-900/80 border border-slate-800 rounded-xl p-4 shadow-lg space-y-2">
                  <div className="flex items-center justify-between border-b border-slate-800 pb-2">
                    <span className="text-sm font-bold text-white">{diffResult.target?.domain} (Prospect)</span>
                    <span className="text-xs font-mono text-rose-400 font-bold">{diffResult.target?.lcp_seconds}s LCP</span>
                  </div>
                  <div className="text-xs space-y-1 text-slate-300">
                    <div>Monthly Latency Loss: <strong className="text-rose-400">${diffResult.target?.monthly_loss_usd?.toLocaleString()}/mo</strong></div>
                    <div>Detected Stack: {diffResult.target?.detected_stack?.join(', ') || 'Standard Web'}</div>
                    <div className="text-slate-500 font-mono text-[10px]">Evidence ID: {diffResult.target?.evidence_id}</div>
                  </div>
                </div>

                {/* Competitor Card */}
                <div className="bg-slate-900/80 border border-slate-800 rounded-xl p-4 shadow-lg space-y-2">
                  <div className="flex items-center justify-between border-b border-slate-800 pb-2">
                    <span className="text-sm font-bold text-white">{diffResult.competitor?.domain} (Competitor)</span>
                    <span className="text-xs font-mono text-emerald-400 font-bold">{diffResult.competitor?.lcp_seconds}s LCP</span>
                  </div>
                  <div className="text-xs space-y-1 text-slate-300">
                    <div>Monthly Latency Loss: <strong className="text-emerald-400">${diffResult.competitor?.monthly_loss_usd?.toLocaleString()}/mo</strong></div>
                    <div>Detected Stack: {diffResult.competitor?.detected_stack?.join(', ') || 'Standard Web'}</div>
                    <div className="text-slate-500 font-mono text-[10px]">Evidence ID: {diffResult.competitor?.evidence_id}</div>
                  </div>
                </div>
              </div>
            </div>
          )}
        </div>
      )}

      {/* =========================================================================
          MODE: HUMAN TOUCH INTERACTIVE BROWSER
         ========================================================================= */}
      {activeMode === 'touch' && (
        <div className="space-y-6">
          <div className="bg-slate-900/80 border border-slate-800 rounded-xl p-5 shadow-xl space-y-4">
            <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
              <div>
                <h2 className="text-lg font-bold text-white flex items-center gap-2">
                  <MousePointerClick className="h-5 w-5 text-indigo-400" />
                  Live Interactive Browser with Human Touch
                </h2>
                <p className="text-xs text-slate-400">
                  Click directly on the viewport to dispatch coordinate clicks (x, y), type into active elements, or launch a physical Chrome window on Mac to solve puzzles or log in.
                </p>
              </div>

              <button
                onClick={handleLaunchHeaded}
                className="px-4 py-2 bg-emerald-600 hover:bg-emerald-500 text-white rounded-lg text-xs font-semibold flex items-center gap-2 transition-all shadow-md shadow-emerald-600/30"
              >
                <ExternalLink className="h-4 w-4" />
                Launch Physical Chrome (Desktop Takeover)
              </button>
            </div>

            {headedStatus && (
              <div className="p-3 bg-emerald-950/40 border border-emerald-500/30 rounded-lg text-xs text-emerald-300 font-mono">
                {headedStatus}
              </div>
            )}

            {/* Navigation Bar */}
            <div className="flex flex-wrap items-center gap-3 pt-2 border-t border-slate-800">
              <div className="flex-1 min-w-[280px]">
                <input
                  type="text"
                  value={touchUrl}
                  onChange={e => setTouchUrl(e.target.value)}
                  placeholder="https://example.com"
                  className="w-full bg-slate-950 border border-slate-700 rounded-lg px-4 py-2 text-sm text-slate-200 focus:outline-none focus:border-indigo-500 font-mono"
                />
              </div>

              <button
                onClick={handleTouchNavigate}
                disabled={touchLoading}
                className="px-5 py-2 bg-indigo-600 hover:bg-indigo-500 text-white rounded-lg text-sm font-semibold flex items-center gap-2 transition-all disabled:opacity-50"
              >
                {touchLoading ? <RefreshCw className="h-4 w-4 animate-spin" /> : <Globe className="h-4 w-4" />}
                Navigate & Sync
              </button>

              <button
                onClick={() => handleTouchScroll('down')}
                disabled={touchLoading || !touchNavResult}
                className="px-3 py-2 bg-slate-800 hover:bg-slate-700 text-slate-200 rounded-lg text-xs font-medium"
              >
                Scroll Down &darr;
              </button>

              <button
                onClick={() => handleTouchScroll('up')}
                disabled={touchLoading || !touchNavResult}
                className="px-3 py-2 bg-slate-800 hover:bg-slate-700 text-slate-200 rounded-lg text-xs font-medium"
              >
                Scroll Up &uarr;
              </button>
            </div>

            {/* Keystroke Dispatcher */}
            <div className="flex items-center gap-2 pt-2 border-t border-slate-800/60">
              <input
                type="text"
                value={touchKeystrokes}
                onChange={e => setTouchKeystrokes(e.target.value)}
                onKeyDown={e => { if (e.key === 'Enter') handleTouchType(); }}
                placeholder="Type text or credentials to dispatch into active web page..."
                className="flex-1 bg-slate-950 border border-slate-800 rounded-lg px-3 py-1.5 text-xs text-slate-200 focus:outline-none focus:border-indigo-500"
              />
              <button
                onClick={handleTouchType}
                disabled={touchLoading || !touchKeystrokes.trim()}
                className="px-4 py-1.5 bg-slate-800 hover:bg-slate-700 text-white rounded-lg text-xs font-medium flex items-center gap-1 disabled:opacity-50"
              >
                <Send className="h-3.5 w-3.5" />
                Dispatch Keystrokes
              </button>
            </div>
          </div>

          {/* Interactive Canvas & Diagnostics */}
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            <div className="lg:col-span-2 bg-slate-900/80 border border-slate-800 rounded-xl p-4 shadow-xl">
              <div className="flex items-center justify-between border-b border-slate-800 pb-3 mb-3">
                <span className="text-xs font-mono text-slate-400">
                  Viewport: 1280 &times; 800 &bull; Click anywhere on page for coordinate interaction
                </span>
                {touchNavResult && (
                  <span className="text-xs text-emerald-400 font-semibold flex items-center gap-1">
                    <span className="h-2 w-2 rounded-full bg-emerald-400 animate-pulse" />
                    Human Touch Active
                  </span>
                )}
              </div>

              {touchNavResult?.viewport_screenshot ? (
                <div className="relative border border-slate-700 rounded-lg overflow-hidden bg-black flex justify-center group">
                  <img
                    src={touchNavResult.viewport_screenshot}
                    alt="Interactive Viewport"
                    onClick={handleTouchClick}
                    className="max-w-full h-auto cursor-crosshair select-none transition-opacity"
                  />
                  {touchLoading && (
                    <div className="absolute inset-0 bg-slate-950/60 backdrop-blur-sm flex items-center justify-center">
                      <div className="flex items-center gap-2 text-indigo-400 font-mono text-sm">
                        <RefreshCw className="h-5 w-5 animate-spin" />
                        Synchronizing DOM with Chromium...
                      </div>
                    </div>
                  )}
                </div>
              ) : (
                <div className="h-96 border border-dashed border-slate-800 rounded-lg flex flex-col items-center justify-center text-slate-500 gap-3">
                  <Camera className="h-10 w-10 text-slate-600" />
                  <p className="text-sm">Enter a target URL above and click "Navigate & Sync" to begin interactive browsing.</p>
                </div>
              )}
            </div>

            {/* DOM Extraction & Action Log */}
            <div className="space-y-4">
              <div className="bg-slate-900/80 border border-slate-800 rounded-xl p-4 shadow-xl space-y-3">
                <h3 className="text-xs font-mono uppercase tracking-wider text-slate-400 border-b border-slate-800 pb-2">
                  DOM Intelligence Feed
                </h3>
                {touchNavResult ? (
                  <div className="text-xs space-y-2 text-slate-300">
                    <div><strong>Title:</strong> {touchNavResult.title || 'N/A'}</div>
                    <div>
                      <strong>Detected Stack:</strong>
                      <div className="flex flex-wrap gap-1 mt-1">
                        {touchNavResult.detected_stack?.map((s: string, idx: number) => (
                          <span key={idx} className="px-2 py-0.5 bg-indigo-950 border border-indigo-700/50 text-indigo-300 rounded text-[10px]">
                            {s}
                          </span>
                        ))}
                      </div>
                    </div>
                    {touchNavResult.emails?.length > 0 && (
                      <div className="space-y-1">
                        <strong className="text-slate-300">Emails:</strong>
                        <div className="flex flex-wrap gap-1.5 mt-1">
                          {touchNavResult.emails.map((em: string, idx: number) => (
                            <CopyableEmail key={idx} email={em} />
                          ))}
                        </div>
                      </div>
                    )}
                    {touchNavResult.phones?.length > 0 && (
                      <div className="space-y-1">
                        <strong className="text-slate-300">Phones:</strong>
                        <div className="flex flex-wrap gap-1.5 mt-1">
                          {touchNavResult.phones.map((ph: string, idx: number) => (
                            <CopyablePhone key={idx} phone={ph} />
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                ) : (
                  <div className="text-xs text-slate-500">No active DOM synchronized yet.</div>
                )}
              </div>

              <div className="bg-slate-900/80 border border-slate-800 rounded-xl p-4 shadow-xl space-y-2">
                <h3 className="text-xs font-mono uppercase tracking-wider text-slate-400 border-b border-slate-800 pb-2">
                  Human Touch Event Log
                </h3>
                <div className="h-48 overflow-y-auto font-mono text-[11px] text-slate-400 space-y-1">
                  {touchLogs.length === 0 ? (
                    <div className="text-slate-600 italic">No events recorded.</div>
                  ) : (
                    touchLogs.map((log, i) => (
                      <div key={i} className="text-slate-300 border-b border-slate-800/40 pb-0.5">{log}</div>
                    ))
                  )}
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* =========================================================================
          MODE: SPECIALIZED SWARM PODS (MULTI-AGENT TEAMING)
         ========================================================================= */}
      {activeMode === 'pods' && (
        <div className="space-y-6">
          <div className="bg-slate-900/80 border border-slate-800 rounded-xl p-5 shadow-xl space-y-4">
            <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
              <div>
                <h2 className="text-lg font-bold text-white flex items-center gap-2">
                  <Users className="h-5 w-5 text-indigo-400" />
                  Specialized Autonomous Swarm Pods
                </h2>
                <p className="text-xs text-slate-400">
                  Deconstructs business development into 5 institutional specialist pods operating concurrently.
                </p>
              </div>

              <button
                onClick={handleRunPods}
                disabled={podsLoading}
                className="px-5 py-2.5 bg-indigo-600 hover:bg-indigo-500 text-white rounded-lg text-sm font-semibold flex items-center gap-2 transition-all shadow-lg shadow-indigo-600/30 disabled:opacity-50"
              >
                {podsLoading ? <RefreshCw className="h-4 w-4 animate-spin" /> : <Play className="h-4 w-4" />}
                Execute All 5 Pods
              </button>
            </div>

            <div className="flex flex-wrap items-center gap-3 pt-2 border-t border-slate-800">
              <div className="flex-1 min-w-[200px]">
                <label className="text-[11px] text-slate-400 font-mono block mb-1">Target Prospect Domain</label>
                <input
                  type="text"
                  value={podsDomain}
                  onChange={e => setPodsDomain(e.target.value)}
                  placeholder="e.g. prospectcompany.com"
                  className="w-full bg-slate-950 border border-slate-700 rounded-lg px-3 py-1.5 text-xs text-slate-200 font-mono placeholder:text-slate-600"
                />
              </div>

              <div className="flex-1 min-w-[200px]">
                <label className="text-[11px] text-slate-400 font-mono block mb-1">Benchmark Peer / Competitor</label>
                <input
                  type="text"
                  value={podsCompetitor}
                  onChange={e => setPodsCompetitor(e.target.value)}
                  placeholder="e.g. stripe.com"
                  className="w-full bg-slate-950 border border-slate-700 rounded-lg px-3 py-1.5 text-xs text-slate-200 font-mono placeholder:text-slate-600"
                />
              </div>
            </div>
          </div>

          {/* 5 Pods Grid Display */}
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
            {/* Pod 1 */}
            <div className="bg-slate-900/80 border border-slate-800 rounded-xl p-4 shadow-xl space-y-3">
              <div className="flex items-center justify-between border-b border-slate-800 pb-2">
                <span className="text-xs font-mono text-cyan-400 font-bold uppercase">Pod 1: Sourcing Scout</span>
                <span className="text-[10px] bg-cyan-950 text-cyan-300 px-2 py-0.5 rounded border border-cyan-800">SEC EDGAR</span>
              </div>
              <p className="text-xs text-slate-400">Scours venture capital Form D filings for newly funded growth rounds.</p>
              <div className="p-3 bg-slate-950 rounded-lg text-xs space-y-1">
                <div>Leads Sourced: <strong className="text-white">{podsResult?.sourcing?.leads_found ?? 3} accounts</strong></div>
                <div>Filter: <span className="text-slate-400">Equity Financing &gt; $5M</span></div>
              </div>
            </div>

            {/* Pod 2 */}
            <div className="bg-slate-900/80 border border-slate-800 rounded-xl p-4 shadow-xl space-y-3">
              <div className="flex items-center justify-between border-b border-slate-800 pb-2">
                <span className="text-xs font-mono text-amber-400 font-bold uppercase">Pod 2: Forensics Engineer</span>
                <span className="text-[10px] bg-amber-950 text-amber-300 px-2 py-0.5 rounded border border-amber-800">Headless Chrome</span>
              </div>
              <p className="text-xs text-slate-400">Inspects SPA virtual DOM, Core Web Vitals, and architecture debt.</p>
              <div className="p-3 bg-slate-950 rounded-lg text-xs space-y-1">
                <div>LCP Latency: <strong className="text-rose-400">{podsResult?.forensics?.measured_lcp_seconds ?? 3.8}s</strong></div>
                <div>Detected Stack: <span className="text-slate-300">{podsResult?.forensics?.detected_stack?.join(', ') || 'Next.js, React'}</span></div>
              </div>
            </div>

            {/* Pod 3 */}
            <div className="bg-slate-900/80 border border-slate-800 rounded-xl p-4 shadow-xl space-y-3">
              <div className="flex items-center justify-between border-b border-slate-800 pb-2">
                <span className="text-xs font-mono text-emerald-400 font-bold uppercase">Pod 3: Deal Strategist</span>
                <span className="text-[10px] bg-emerald-950 text-emerald-300 px-2 py-0.5 rounded border border-emerald-800">Bayesian Model</span>
              </div>
              <p className="text-xs text-slate-400">Computes P(Close) win probability and competitive conversion deficit.</p>
              <div className="p-3 bg-slate-950 rounded-lg text-xs space-y-1">
                <div>Win Prob (P(Close)): <strong className="text-emerald-400">{podsResult?.deal_strategy?.p_close_percent ?? 82.5}%</strong></div>
                <div>Expected Value: <strong className="text-white">${podsResult?.deal_strategy?.expected_deal_value_usd?.toLocaleString() ?? '58,000'}</strong></div>
              </div>
            </div>

            {/* Pod 4 */}
            <div className="bg-slate-900/80 border border-slate-800 rounded-xl p-4 shadow-xl space-y-3">
              <div className="flex items-center justify-between border-b border-slate-800 pb-2">
                <span className="text-xs font-mono text-indigo-400 font-bold uppercase">Pod 4: Deliverability Sentinel</span>
                <span className="text-[10px] bg-indigo-950 text-indigo-300 px-2 py-0.5 rounded border border-indigo-800">Sigmoid Ramp</span>
              </div>
              <p className="text-xs text-slate-400">Controls mailbox warmup curves, SPF/DKIM validation, and pacing.</p>
              <div className="p-3 bg-slate-950 rounded-lg text-xs space-y-1">
                <div>Safe Daily Volume: <strong className="text-indigo-300">{podsResult?.deliverability?.safe_daily_dispatch_volume ?? 42} emails/day</strong></div>
                <div>Deliverability Health: <span className="text-emerald-400 font-semibold">OPTIMAL (100%)</span></div>
              </div>
            </div>

            {/* Pod 5 */}
            <div className="bg-slate-900/80 border border-slate-800 rounded-xl p-4 shadow-xl space-y-3 md:col-span-2 lg:col-span-2">
              <div className="flex items-center justify-between border-b border-slate-800 pb-2">
                <span className="text-xs font-mono text-purple-400 font-bold uppercase">Pod 5: Objection Negotiator</span>
                <span className="text-[10px] bg-purple-950 text-purple-300 px-2 py-0.5 rounded border border-purple-800">Rebuttal Engine</span>
              </div>
              <p className="text-xs text-slate-400">Triages incoming prospect pushback and generates evidence-anchored counter-pitches.</p>
              <div className="p-3 bg-slate-950 rounded-lg text-xs space-y-2">
                <div className="text-slate-400">Sample Objection: <em>"We already have an in-house engineering squad."</em></div>
                <div className="text-indigo-300 font-semibold">Strategy: Frame agency as specialized burst acceleration rather than employee replacement.</div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* =========================================================================
          MODE: BOARDROOM TEARDOWN DECK EXPORTER
         ========================================================================= */}
      {activeMode === 'deck' && (
        <div className="space-y-6">
          <div className="bg-slate-900/80 border border-slate-800 rounded-xl p-5 shadow-xl space-y-4">
            <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
              <div>
                <h2 className="text-lg font-bold text-white flex items-center gap-2">
                  <Printer className="h-5 w-5 text-indigo-400" />
                  Executive 3-Page Boardroom Teardown Deck Exporter
                </h2>
                <p className="text-xs text-slate-400">
                  Exports a boardroom-ready 3-page audit deck in clean print-ready HTML/PDF with KaTeX math equations and 90-day modernization milestones.
                </p>
              </div>

              <button
                onClick={handleExportDeck}
                disabled={deckLoading}
                className="px-5 py-2.5 bg-indigo-600 hover:bg-indigo-500 text-white rounded-lg text-sm font-semibold flex items-center gap-2 transition-all shadow-lg shadow-indigo-600/30 disabled:opacity-50"
              >
                {deckLoading ? <RefreshCw className="h-4 w-4 animate-spin" /> : <Printer className="h-4 w-4" />}
                Export 3-Page Deck
              </button>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3 pt-2 border-t border-slate-800">
              <div>
                <label className="text-[11px] text-slate-400 font-mono block mb-1">Target Prospect</label>
                <input
                  type="text"
                  value={deckTarget}
                  onChange={e => setDeckTarget(e.target.value)}
                  placeholder="e.g. prospectcompany.com"
                  className="w-full bg-slate-950 border border-slate-700 rounded-lg px-3 py-1.5 text-xs text-slate-200 font-mono placeholder:text-slate-600"
                />
              </div>

              <div>
                <label className="text-[11px] text-slate-400 font-mono block mb-1">Benchmark Competitor</label>
                <input
                  type="text"
                  value={deckCompetitor}
                  onChange={e => setDeckCompetitor(e.target.value)}
                  placeholder="e.g. stripe.com"
                  className="w-full bg-slate-950 border border-slate-700 rounded-lg px-3 py-1.5 text-xs text-slate-200 font-mono placeholder:text-slate-600"
                />
              </div>

              <div>
                <label className="text-[11px] text-slate-400 font-mono block mb-1">Monthly Visitors</label>
                <input
                  type="number"
                  value={deckVisitors}
                  onChange={e => setDeckVisitors(parseInt(e.target.value) || 50000)}
                  className="w-full bg-slate-950 border border-slate-700 rounded-lg px-3 py-1.5 text-xs text-slate-200 font-mono"
                />
              </div>

              <div>
                <label className="text-[11px] text-slate-400 font-mono block mb-1">Avg Transaction / AOV ($)</label>
                <input
                  type="number"
                  value={deckAov}
                  onChange={e => setDeckAov(parseFloat(e.target.value) || 125)}
                  className="w-full bg-slate-950 border border-slate-700 rounded-lg px-3 py-1.5 text-xs text-slate-200 font-mono"
                />
              </div>
            </div>
          </div>

          {/* Deck Result Card */}
          {deckResult && (
            <div className="bg-slate-900/80 border border-slate-800 rounded-xl p-5 shadow-xl space-y-4">
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-slate-800 pb-3">
                <span className="text-sm font-bold text-white flex items-center gap-2">
                  <CheckCircle2 className="h-4 w-4 text-emerald-400" />
                  Deck Generated: {deckResult.html_filename}
                </span>

                <div className="flex items-center gap-2">
                  <a
                    href={`/api/teardown/deck/view/${deckResult.html_filename}`}
                    target="_blank"
                    rel="noreferrer"
                    className="px-4 py-1.5 bg-slate-800 hover:bg-slate-700 text-white rounded-lg text-xs font-medium flex items-center gap-1.5 transition-colors"
                  >
                    <ExternalLink className="h-3.5 w-3.5" />
                    Open Fullscreen Printable Deck
                  </a>

                  {deckResult.has_pdf && deckResult.pdf_path && (
                    <a
                      href={`/api/teardown/deck/view/${deckResult.html_filename.replace('.html', '.pdf')}`}
                      download
                      className="px-4 py-1.5 bg-emerald-600 hover:bg-emerald-500 text-white rounded-lg text-xs font-semibold flex items-center gap-1.5 transition-colors"
                    >
                      <Download className="h-3.5 w-3.5" />
                      Download PDF
                    </a>
                  )}
                </div>
              </div>

              {/* Embedded Live Preview */}
              <div className="border border-slate-700 rounded-xl overflow-hidden bg-slate-950 h-[650px] shadow-2xl">
                <iframe
                  src={`/api/teardown/deck/view/${deckResult.html_filename}`}
                  title="Teardown Deck Preview"
                  className="w-full h-full border-0"
                />
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
};

