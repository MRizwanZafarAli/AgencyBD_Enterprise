import { useState } from 'react';
import type { FC } from 'react';
import { Send, Shuffle, Play, CheckCircle2 } from 'lucide-react';
import { EspRoutingGraph } from '../charts/EspRoutingGraph';
import { apiFetch, apiErrorMessage } from '../../lib/api';
import { ErrorBanner } from '../shared/ErrorBanner';

export const FleetRouter: FC = () => {
  const [error, setError] = useState('');
  const [spintaxInput, setSpintaxInput] = useState(
    '{Hi|Hello|Hey} {{first_name}}, {noticed|saw|came across} your engineering sprint updates at {{company}}. {Open to taking|Worth exploring} a quick peek at the audit teardown?'
  );
  const [spintaxOutput, setSpintaxOutput] = useState('');
  const [targetMx, setTargetMx] = useState('aspmx.l.google.com');
  const [routeResult, setRouteResult] = useState<any>(null);

  const handleGenerateSpintax = async () => {
    try {
      const res = await apiFetch('/api/native/parse_spintax', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ template_text: spintaxInput })
      });
      const data = await res.json();
      setSpintaxOutput(data.generated_variant);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not reach the API.');
    }
  };

  const handleTestRoute = async () => {
    try {
      setError('');
      const mbRes = await apiFetch('/api/outbound/mailboxes');
      const boxes = mbRes.ok ? await mbRes.json() : [];
      if (!boxes.length) throw new Error('Register a sending mailbox first (Governance > Mailbox Fleet). Routing uses your real mailboxes.');
      const providerName = (esp: string | null) => (esp === 'google' ? 'Google Workspace' : esp === 'microsoft' ? 'Microsoft 365' : 'Custom SMTP');
      const res = await apiFetch('/api/native/route_smartlead', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          recipient_mx_host: targetMx,
          available_inboxes: boxes.map((b: any) => ({ id: String(b.id), email: b.email, provider: providerName(b.esp) }))
        })
      });
      const data = await res.json();
      if (!res.ok) throw new Error(apiErrorMessage(res.status, data));
      setRouteResult(data);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not reach the API.');
    }
  };

  return (
    <div className="space-y-6 animate-fadeIn">
      <ErrorBanner message={error} />
      <div>
        <h1 className="text-2xl font-bold tracking-tight text-white flex items-center space-x-2">
          <span>Fleet Deliverability & ESP Router</span>
          <span className="px-2 py-0.5 rounded-full text-[10px] font-mono bg-cyan-500/10 text-cyan-400 border border-cyan-500/20">
            SMARTLEAD REPLACEMENT
          </span>
        </h1>
        <p className="text-sm text-slate-400 mt-0.5">
          Eliminates domain clustering bans through recursive spintax permutations and provider-matched ESP inbox rotation.
        </p>
      </div>

      {/* Dynamic ESP Routing Diagram */}
      <EspRoutingGraph
        targetMx={targetMx}
        selectedSender={routeResult?.selected_sender_email || ''}
        selectedEsp={routeResult?.selected_esp || 'Google Workspace'}
        deliverabilityBoost={routeResult?.deliverability_boost_pct || '+18% Primary Tab Placement'}
      />

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Panel 1: Recursive Spintax Synthesizer */}
        <div className="glass-panel rounded-2xl p-5 sm:p-6 border border-slate-800 space-y-4">
          <div className="flex items-center space-x-2">
            <Shuffle className="h-5 w-5 text-indigo-400" />
            <h3 className="text-sm font-semibold text-white">Recursive Spintax Synthesizer</h3>
          </div>
          <div>
            <label className="text-xs text-slate-400 font-medium">Input Template (Nested Spintax)</label>
            <textarea
              rows={4}
              value={spintaxInput}
              onChange={(e) => setSpintaxInput(e.target.value)}
              className="w-full bg-slate-900 border border-slate-700/80 rounded-lg p-3 text-xs text-white font-mono mt-1 focus:border-indigo-500 focus:outline-none"
            />
          </div>

          <button
            onClick={handleGenerateSpintax}
            className="w-full bg-indigo-600 hover:bg-indigo-500 text-white font-semibold py-2.5 rounded-lg text-xs flex items-center justify-center space-x-2 transition-all shadow-lg shadow-indigo-600/20"
          >
            <Shuffle className="h-4 w-4" />
            <span>Generate Unique Variant</span>
          </button>

          {spintaxOutput && (
            <div className="p-3.5 bg-slate-900/90 rounded-xl border border-slate-700 space-y-1.5">
              <span className="text-[11px] font-semibold text-emerald-400">Generated Unique Variant:</span>
              <p className="text-xs text-slate-200 font-sans italic">{spintaxOutput}</p>
            </div>
          )}
        </div>

        {/* Panel 2: ESP Provider Router */}
        <div className="glass-panel rounded-2xl p-5 sm:p-6 border border-slate-800 space-y-4">
          <div className="flex items-center space-x-2">
            <Send className="h-5 w-5 text-cyan-400" />
            <h3 className="text-sm font-semibold text-white">ESP Matching Router</h3>
          </div>
          <div>
            <label className="text-xs text-slate-400 font-medium">Recipient Target MX Host</label>
            <input
              value={targetMx}
              onChange={(e) => setTargetMx(e.target.value)}
              className="w-full bg-slate-900 border border-slate-700/80 rounded-lg px-3 py-2 text-sm text-white font-mono mt-1 focus:border-cyan-500 focus:outline-none"
            />
            <span className="text-[10px] text-slate-500 mt-1 block">
              Google Workspace (aspmx.l.google.com) or Microsoft 365 (mail.protection.outlook.com)
            </span>
          </div>

          <button
            onClick={handleTestRoute}
            className="w-full bg-cyan-600 hover:bg-cyan-500 text-white font-semibold py-2.5 rounded-lg text-xs flex items-center justify-center space-x-2 transition-all shadow-lg shadow-cyan-600/20"
          >
            <Play className="h-4 w-4" />
            <span>Compute Optimal Sender Route</span>
          </button>

          {routeResult && (
            <div className="p-3.5 bg-slate-900/90 rounded-xl border border-slate-700 space-y-2 text-xs">
              <div className="flex items-center space-x-2 text-emerald-400 font-semibold">
                <CheckCircle2 className="h-4 w-4 shrink-0" />
                <span>{routeResult.routing_strategy}</span>
              </div>
              <div className="flex justify-between text-slate-400">
                <span>Selected Sender Inbox:</span>
                <span className="font-mono text-white font-bold">{routeResult.selected_sender_email}</span>
              </div>
              <div className="flex justify-between text-slate-400">
                <span>Primary Tab Benefit:</span>
                <span className="font-mono text-cyan-400 font-bold">{routeResult.deliverability_boost_pct}</span>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
