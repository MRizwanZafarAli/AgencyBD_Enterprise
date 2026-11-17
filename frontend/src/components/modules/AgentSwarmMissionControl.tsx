import { useState, useEffect, useCallback } from 'react';
import type { FC } from 'react';
import { 
  Cpu, 
  Activity, 
  Play, 
  Pause, 
  RefreshCw, 
  Zap, 
  Terminal, 
  Layers, 
  Clock 
} from 'lucide-react';
import { Button } from '../ui';
import { apiFetch } from '../../lib/api';

interface AgentStatus {
  name: string;
  role: string;
  description: string;
  state: string;
  subscribed_hooks: string[];
  skills: string[];
  total_actions: number;
  last_action_at: number | null;
}

interface SwarmTelemetry {
  org_id: string;
  swarm_active: boolean;
  total_agents: number;
  agents: AgentStatus[];
  timestamp: number;
}

interface LifecycleEvent {
  id: number;
  event_name: string;
  payload: Record<string, any>;
  source_agent: string | null;
  status: string;
  handlers_count: number;
  duration_ms: number;
  error_message: string | null;
  created_at: string;
}

interface SkillItem {
  name: string;
  description: string;
  input_schema: string;
  output_schema: string;
  timeout_sec: number;
}

export const AgentSwarmMissionControl: FC = () => {
  const [telemetry, setTelemetry] = useState<SwarmTelemetry | null>(null);
  const [events, setEvents] = useState<LifecycleEvent[]>([]);
  const [skills, setSkills] = useState<SkillItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [toggling, setToggling] = useState(false);
  const [activeTab, setActiveTab] = useState<'events' | 'skills' | 'runner'>('events');
  const [selectedSkill, setSelectedSkill] = useState<string>('domain_whois_dns');
  const [testDomain, setTestDomain] = useState<string>('stripe.com');
  const [skillResult, setSkillResult] = useState<any>(null);
  const [runningSkill, setRunningSkill] = useState(false);

  const fetchTelemetry = useCallback(async () => {
    try {
      const res = await apiFetch('/api/v1/swarm/telemetry');
      if (res.ok) {
        const data = await res.json();
        if (data?.telemetry) {
          setTelemetry(data.telemetry);
        }
      }
    } catch (e) {
      console.error('Failed to load swarm telemetry', e);
    }
  }, []);

  const fetchEvents = useCallback(async () => {
    try {
      const res = await apiFetch('/api/v1/swarm/events?limit=25');
      if (res.ok) {
        const data = await res.json();
        if (data?.events) {
          setEvents(data.events);
        }
      }
    } catch (e) {
      console.error('Failed to load lifecycle events', e);
    }
  }, []);

  const fetchSkills = useCallback(async () => {
    try {
      const res = await apiFetch('/api/v1/swarm/skills');
      if (res.ok) {
        const data = await res.json();
        if (data?.skills) {
          setSkills(data.skills);
        }
      }
    } catch (e) {
      console.error('Failed to load skills registry', e);
    }
  }, []);

  const refreshAll = useCallback(async () => {
    setLoading(true);
    await Promise.all([fetchTelemetry(), fetchEvents(), fetchSkills()]);
    setLoading(false);
  }, [fetchTelemetry, fetchEvents, fetchSkills]);

  useEffect(() => {
    refreshAll();
    const interval = setInterval(() => {
      fetchTelemetry();
      fetchEvents();
    }, 4000);
    return () => clearInterval(interval);
  }, [refreshAll, fetchTelemetry, fetchEvents]);

  const toggleSwarm = async () => {
    if (!telemetry) return;
    setToggling(true);
    try {
      const targetState = !telemetry.swarm_active;
      const res = await apiFetch('/api/v1/swarm/activate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ activate: targetState }),
      });
      if (res.ok) {
        await fetchTelemetry();
      }
    } catch (e) {
      console.error('Error toggling swarm autonomy', e);
    } finally {
      setToggling(false);
    }
  };

  const runTestSkill = async () => {
    setRunningSkill(true);
    setSkillResult(null);
    try {
      let params: Record<string, any> = {};
      if (selectedSkill === 'domain_whois_dns' || selectedSkill === 'waterfall_enrichment') {
        params = { domain: testDomain };
      } else if (selectedSkill === 'sovereign_lighthouse_audit') {
        params = { url_or_domain: testDomain };
      } else if (selectedSkill === 'deliverability_gate') {
        params = {
          recipient_email: `contact@${testDomain}`,
          subject: 'Engineering inquiry',
          body: 'Hi team, checking on site performance.',
        };
      } else if (selectedSkill === 'objection_classifier') {
        params = {
          reply_body: 'We are currently focused on our core sprint, ping us in Q4.',
        };
      }

      const res = await apiFetch('/api/v1/swarm/skills/run', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          skill_name: selectedSkill,
          params,
        }),
      });
      if (res.ok) {
        const data = await res.json();
        setSkillResult(data.result);
        await fetchEvents();
      } else {
        const errData = await res.json().catch(() => ({}));
        setSkillResult({ error: errData?.detail || 'Skill execution returned non-200' });
      }
    } catch (err: any) {
      setSkillResult({ error: err?.message || 'Skill execution failed' });
    } finally {
      setRunningSkill(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* Top Banner & Swarm Autonomy Controller */}
      <div className="flex flex-wrap items-center justify-between gap-4 p-5 rounded-2xl bg-slate-900/80 border border-amber-500/30 backdrop-blur-md shadow-2xl">
        <div className="flex items-center gap-4">
          <div className="w-12 h-12 rounded-xl bg-gradient-to-br from-amber-500/20 to-amber-700/30 border border-amber-500/40 flex items-center justify-center text-amber-400 shadow-inner">
            <Cpu className="w-6 h-6 animate-pulse" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h2 className="text-xl font-bold tracking-tight text-white font-sans">
                Autonomous BD Agent Swarm
              </h2>
              <span className={`px-2.5 py-0.5 rounded-full text-xs font-semibold uppercase tracking-wider ${
                telemetry?.swarm_active
                  ? 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/40'
                  : 'bg-slate-700/50 text-slate-400 border border-slate-600/50'
              }`}>
                {telemetry?.swarm_active ? 'SWARM ONLINE' : 'STANDBY'}
              </span>
            </div>
            <p className="text-sm text-slate-400 font-sans mt-0.5">
              8 specialized micro-agents orchestrated across 12 event-driven lifecycle hooks with $0-cost sovereign skills.
            </p>
          </div>
        </div>

        <div className="flex items-center gap-3">
          <Button
            variant="secondary"
            onClick={refreshAll}
            disabled={loading}
            className="flex items-center gap-1.5 text-xs py-2 px-3 border border-slate-700 hover:border-slate-500"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin text-amber-400' : ''}`} />
            Refresh
          </Button>

          <Button
            variant={telemetry?.swarm_active ? 'danger' : 'primary'}
            onClick={toggleSwarm}
            disabled={toggling}
            className={`flex items-center gap-2 text-sm font-semibold py-2 px-4 shadow-lg transition-all ${
              telemetry?.swarm_active
                ? 'bg-rose-900/50 hover:bg-rose-800/80 border border-rose-500/40 text-rose-200'
                : 'bg-amber-500 hover:bg-amber-400 text-slate-950 font-bold'
            }`}
          >
            {telemetry?.swarm_active ? (
              <>
                <Pause className="w-4 h-4 fill-current" />
                Pause Autonomous Swarm
              </>
            ) : (
              <>
                <Play className="w-4 h-4 fill-current" />
                Activate Autonomous Swarm
              </>
            )}
          </Button>
        </div>
      </div>

      {/* 8 Agent Telemetry Grid */}
      <div>
        <div className="flex items-center justify-between mb-3">
          <h3 className="text-sm font-semibold uppercase tracking-wider text-slate-400 flex items-center gap-2">
            <Activity className="w-4 h-4 text-amber-400" />
            Active Micro-Agent Swarm Roster ({telemetry?.agents?.length || 8})
          </h3>
          <span className="text-xs text-slate-400 font-mono">
            EventBus Pub/Sub: <span className="text-emerald-400">Connected</span>
          </span>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          {telemetry?.agents?.map((agent) => (
            <div
              key={agent.name}
              className="p-4 rounded-xl bg-slate-900/60 border border-slate-800 hover:border-amber-500/40 transition-all duration-200 flex flex-col justify-between group hover:shadow-lg hover:shadow-amber-500/5 backdrop-blur-sm"
            >
              <div>
                <div className="flex items-start justify-between gap-2 mb-2">
                  <div className="font-semibold text-white group-hover:text-amber-300 transition-colors text-sm">
                    {agent.role}
                  </div>
                  <span className={`text-[10px] font-mono px-2 py-0.5 rounded-md font-bold uppercase tracking-wider ${
                    agent.state === 'running'
                      ? 'bg-amber-500/20 text-amber-300 border border-amber-500/30 animate-pulse'
                      : agent.state === 'error'
                      ? 'bg-rose-500/20 text-rose-300 border border-rose-500/30'
                      : 'bg-slate-800/80 text-emerald-400 border border-emerald-500/20'
                  }`}>
                    {agent.state}
                  </span>
                </div>

                <p className="text-xs text-slate-400 line-clamp-2 mb-3">
                  {agent.description}
                </p>

                {/* Subscribed Hooks */}
                <div className="mb-2">
                  <span className="text-[10px] uppercase font-bold text-slate-400 block mb-1">
                    Listens to Hooks:
                  </span>
                  <div className="flex flex-wrap gap-1">
                    {agent.subscribed_hooks.length > 0 ? (
                      agent.subscribed_hooks.map((h) => (
                        <span
                          key={h}
                          className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-slate-800 text-amber-300/90 border border-slate-700/60"
                        >
                          {h.replace('on_', '')}
                        </span>
                      ))
                    ) : (
                      <span className="text-[10px] text-slate-400 italic">Global overseer</span>
                    )}
                  </div>
                </div>
              </div>

              <div className="pt-3 border-t border-slate-800/80 flex items-center justify-between text-xs text-slate-400">
                <span className="flex items-center gap-1 font-mono">
                  <Zap className="w-3 h-3 text-amber-400" />
                  {agent.total_actions} actions
                </span>
                <span className="text-[11px] text-slate-400">
                  {agent.skills.length} skills
                </span>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Lower Section: Tabs for Lifecycle Events & Modular Skills */}
      <div className="rounded-2xl bg-slate-900/70 border border-slate-800 backdrop-blur-md overflow-hidden">
        <div className="flex items-center gap-2 border-b border-slate-800 px-4 pt-3 bg-slate-950/40">
          <button
            onClick={() => setActiveTab('events')}
            className={`flex items-center gap-2 px-4 py-2.5 text-xs font-semibold tracking-wide border-b-2 transition-all ${
              activeTab === 'events'
                ? 'border-amber-400 text-amber-300 font-bold'
                : 'border-transparent text-slate-400 hover:text-slate-200'
            }`}
          >
            <Clock className="w-3.5 h-3.5" />
            Live Lifecycle Event Stream ({events.length})
          </button>

          <button
            onClick={() => setActiveTab('skills')}
            className={`flex items-center gap-2 px-4 py-2.5 text-xs font-semibold tracking-wide border-b-2 transition-all ${
              activeTab === 'skills'
                ? 'border-amber-400 text-amber-300 font-bold'
                : 'border-transparent text-slate-400 hover:text-slate-200'
            }`}
          >
            <Layers className="w-3.5 h-3.5" />
            Modular Skills Registry ({skills.length})
          </button>

          <button
            onClick={() => setActiveTab('runner')}
            className={`flex items-center gap-2 px-4 py-2.5 text-xs font-semibold tracking-wide border-b-2 transition-all ${
              activeTab === 'runner'
                ? 'border-amber-400 text-amber-300 font-bold'
                : 'border-transparent text-slate-400 hover:text-slate-200'
            }`}
          >
            <Terminal className="w-3.5 h-3.5" />
            Interactive Skill Test Sandbox
          </button>
        </div>

        <div className="p-4">
          {/* TAB 1: Real-time Event Stream */}
          {activeTab === 'events' && (
            <div className="space-y-2">
              {events.length === 0 ? (
                <div className="text-center py-8 text-sm text-slate-400">
                  No lifecycle events recorded yet. Source a lead or run a skill to trigger real-time events.
                </div>
              ) : (
                <div className="divide-y divide-slate-800/60 max-h-96 overflow-y-auto">
                  {events.map((ev) => (
                    <div key={ev.id} className="py-2.5 px-3 flex items-center justify-between gap-4 hover:bg-slate-800/30 rounded-lg transition-colors">
                      <div className="flex items-center gap-3">
                        <span className={`w-2 h-2 rounded-full ${
                          ev.status === 'processed' || ev.status === 'success'
                            ? 'bg-emerald-400 shadow-sm shadow-emerald-400/50'
                            : 'bg-amber-400'
                        }`} />
                        <div>
                          <div className="flex items-center gap-2">
                            <span className="font-mono text-xs font-bold text-amber-300">
                              {ev.event_name}
                            </span>
                            <span className="text-[10px] text-slate-400 font-mono">
                              via {ev.source_agent || 'System'}
                            </span>
                          </div>
                          <div className="text-xs text-slate-400 truncate max-w-md mt-0.5">
                            {ev.payload?.domain && <span className="text-slate-300 font-medium">Domain: {ev.payload.domain} </span>}
                            {ev.payload?.company_name && <span>({ev.payload.company_name}) </span>}
                            {ev.payload?.recipient_email && <span>Recipient: {ev.payload.recipient_email} </span>}
                            {ev.payload?.pitch_angle && <span className="italic text-slate-400">"{ev.payload.pitch_angle}"</span>}
                          </div>
                        </div>
                      </div>

                      <div className="flex items-center gap-3 text-right">
                        <span className="text-[11px] text-slate-400 font-mono">
                          {ev.duration_ms ? `${Math.round(ev.duration_ms)}ms` : '<1ms'}
                        </span>
                        <span className="text-[11px] text-slate-400 font-mono whitespace-nowrap">
                          {ev.created_at?.split(' ')[1] || ev.created_at}
                        </span>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* TAB 2: Skills Registry */}
          {activeTab === 'skills' && (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {skills.map((s) => (
                <div key={s.name} className="p-4 rounded-xl bg-slate-950/40 border border-slate-800 hover:border-slate-700">
                  <div className="flex items-center justify-between mb-1.5">
                    <span className="font-mono text-sm font-bold text-amber-400">
                      {s.name}
                    </span>
                    <span className="text-[11px] text-slate-400 font-mono">
                      Timeout: {s.timeout_sec}s
                    </span>
                  </div>
                  <p className="text-xs text-slate-300 mb-3">
                    {s.description}
                  </p>
                  <div className="flex items-center gap-2 text-[11px] font-mono text-slate-400">
                    <span className="bg-slate-800 px-2 py-0.5 rounded text-slate-300">
                      In: {s.input_schema}
                    </span>
                    <span>→</span>
                    <span className="bg-slate-800 px-2 py-0.5 rounded text-slate-300">
                      Out: {s.output_schema}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          )}

          {/* TAB 3: Interactive Sandbox */}
          {activeTab === 'runner' && (
            <div className="space-y-4">
              <div className="flex flex-wrap items-center gap-3">
                <select
                  value={selectedSkill}
                  onChange={(e) => setSelectedSkill(e.target.value)}
                  className="bg-slate-950 border border-slate-700 rounded-lg px-3 py-2 text-xs text-white font-mono focus:border-amber-400 outline-none"
                >
                  {skills.map((s) => (
                    <option key={s.name} value={s.name}>
                      {s.name}
                    </option>
                  ))}
                </select>

                <input
                  type="text"
                  value={testDomain}
                  onChange={(e) => setTestDomain(e.target.value)}
                  placeholder="Target domain (e.g. stripe.com)"
                  className="bg-slate-950 border border-slate-700 rounded-lg px-3 py-2 text-xs text-white font-mono flex-1 min-w-[200px] focus:border-amber-400 outline-none"
                />

                <Button
                  variant="primary"
                  onClick={runTestSkill}
                  disabled={runningSkill}
                  className="text-xs py-2 px-4 bg-amber-500 hover:bg-amber-400 text-slate-950 font-bold"
                >
                  {runningSkill ? 'Executing Skill…' : 'Run Skill'}
                </Button>
              </div>

              {skillResult && (
                <div className="mt-3 p-4 rounded-xl bg-slate-950 border border-slate-800 font-mono text-xs overflow-x-auto">
                  <div className="text-slate-400 text-[11px] mb-1">Execution Output:</div>
                  <pre className="text-emerald-300">{JSON.stringify(skillResult, null, 2)}</pre>
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
