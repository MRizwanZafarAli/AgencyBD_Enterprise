import { useState } from 'react';
import type { FC } from 'react';
import { Terminal, Play, RefreshCw, ExternalLink } from 'lucide-react';
import { apiFetch } from '../../lib/api';

const ENDPOINTS = [
  { method: 'POST', path: '/api/sourcing/run', desc: 'Google Maps Open Scraper (Zero Places API Cost)', sample: '{"channel": "google_maps", "query": "Custom Software Agency", "location": "Austin, TX", "limit": 3}' },
  { method: 'POST', path: '/api/sourcing/linkedin/people', desc: 'Google X-Ray Dorking for LinkedIn Decision Makers', sample: '{"company_name": "Resend", "titles": ["CTO", "Founder"], "location": "United States", "limit": 2}' },
  { method: 'POST', path: '/api/native/waterfall_enrich', desc: 'Clay-Free Waterfall Permutation & SMTP RFC 5322 Handshake', sample: '{"first_name": "Jane", "last_name": "Doe", "company_name": "Example Co", "domain": "example.com", "title": "CEO"}' },
  { method: 'POST', path: '/api/native/score_copy', desc: 'Lavender.ai Flesch-Kincaid & 100+ Spam Word Filter', sample: '{"subject": "quick question", "body": "Hi Jane, I noticed your site takes four seconds to load on mobile."}' },
  { method: 'POST', path: '/api/native/route_smartlead', desc: 'Smartlead Google-to-Google & M365-to-M365 Matcher', sample: '{"recipient_mx_host": "aspmx.l.google.com", "available_inboxes": [{"id": 1, "email": "alex@apex.io", "esp": "Google Workspace"}]}' },
  { method: 'POST', path: '/api/native/parse_spintax', desc: 'Recursive Anti-Clustering Spintax Variant Generator', sample: '{"template_text": "{Hi|Hey|Hello} {{first_name}}, {saw|noticed} your work."}' },
  { method: 'GET', path: '/healthz/live', desc: 'Kubernetes & Docker Microservice Liveness Probe', sample: '' }
];

export const ApiExplorer: FC = () => {
  const [selectedEndpoint, setSelectedEndpoint] = useState(ENDPOINTS[0]);
  const [requestBody, setRequestBody] = useState(ENDPOINTS[0].sample);
  const [responseOutput, setResponseOutput] = useState<any>(null);
  const [loading, setLoading] = useState(false);

  const handleSelect = (ep: typeof ENDPOINTS[0]) => {
    setSelectedEndpoint(ep);
    setRequestBody(ep.sample);
    setResponseOutput(null);
  };

  const handleExecute = async () => {
    setLoading(true);
    try {
      let res;
      if (selectedEndpoint.method === 'GET') {
        res = await apiFetch(selectedEndpoint.path);
      } else {
        res = await apiFetch(selectedEndpoint.path, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: requestBody
        });
      }
      const data = await res.json();
      setResponseOutput(data);
    } catch (err: any) {
      setResponseOutput({ error: err.message, note: 'Tested through native proxy' });
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-6 animate-fadeIn">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-white flex items-center space-x-2">
            <span>Developer REST API Console & Explorer</span>
            <span className="px-2 py-0.5 rounded-full text-[10px] font-mono bg-indigo-500/10 text-indigo-400 border border-indigo-500/20">
              FASTAPI CORE
            </span>
          </h1>
          <p className="text-sm text-slate-400 mt-0.5">
            Test and inspect all microservice endpoints directly from your browser with zero postman requirements.
          </p>
        </div>
        <a
          href="/docs"
          target="_blank"
          rel="noreferrer"
          className="px-3.5 py-2 rounded-xl bg-slate-900 border border-slate-700 hover:border-slate-600 text-slate-200 text-xs font-semibold flex items-center space-x-1.5 transition-all self-start sm:self-auto"
        >
          <span>Open Full Interactive Swagger Docs</span>
          <ExternalLink className="h-3.5 w-3.5 text-indigo-400" />
        </a>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Endpoint List */}
        <div className="glass-panel rounded-2xl p-4 border border-slate-800 space-y-2">
          <div className="text-xs font-semibold text-slate-400 px-2 uppercase font-mono">Available Endpoints</div>
          <div className="space-y-1">
            {ENDPOINTS.map((ep, i) => (
              <button
                key={i}
                onClick={() => handleSelect(ep)}
                className={`w-full text-left p-2.5 rounded-xl text-xs font-mono transition-all flex flex-col space-y-1 ${
                  selectedEndpoint.path === ep.path
                    ? 'bg-indigo-600/20 border border-indigo-500/40 text-white'
                    : 'text-slate-400 hover:bg-slate-900/60 hover:text-slate-200'
                }`}
              >
                <div className="flex items-center space-x-2">
                  <span className={`px-1.5 py-0.5 rounded text-[10px] font-bold ${
                    ep.method === 'GET' ? 'bg-emerald-500/20 text-emerald-300' : 'bg-cyan-500/20 text-cyan-300'
                  }`}>
                    {ep.method}
                  </span>
                  <span className="font-semibold text-white truncate">{ep.path}</span>
                </div>
                <div className="text-[10px] font-sans text-slate-400 line-clamp-1">{ep.desc}</div>
              </button>
            ))}
          </div>
        </div>

        {/* Console Request & Response */}
        <div className="lg:col-span-2 glass-panel rounded-2xl p-5 sm:p-6 border border-slate-800 space-y-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-2">
              <Terminal className="h-5 w-5 text-indigo-400" />
              <h3 className="text-sm font-semibold text-white font-mono">{selectedEndpoint.method} {selectedEndpoint.path}</h3>
            </div>
            <button
              onClick={handleExecute}
              disabled={loading}
              className="px-3 py-1.5 bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-semibold rounded-lg flex items-center space-x-1.5 shadow-md shadow-indigo-600/20 transition-all"
            >
              {loading ? <RefreshCw className="h-3.5 w-3.5 animate-spin" /> : <Play className="h-3.5 w-3.5" />}
              <span>Execute Request</span>
            </button>
          </div>

          <p className="text-xs text-slate-400">{selectedEndpoint.desc}</p>

          {selectedEndpoint.method === 'POST' && (
            <div>
              <label className="text-xs text-slate-400 font-medium">Request Body (JSON)</label>
              <textarea
                rows={4}
                value={requestBody}
                onChange={(e) => setRequestBody(e.target.value)}
                className="w-full bg-slate-950 border border-slate-800 rounded-lg p-3 text-xs text-emerald-300 font-mono mt-1 focus:border-indigo-500 focus:outline-none"
              />
            </div>
          )}

          <div>
            <label className="text-xs text-slate-400 font-medium">Live Microservice Response</label>
            <div className="mt-1 p-3.5 bg-slate-950 rounded-xl border border-slate-800 font-mono text-xs text-slate-300 min-h-[140px] max-h-[300px] overflow-y-auto">
              {loading ? (
                <div className="flex items-center space-x-2 text-indigo-400 py-6 justify-center">
                  <RefreshCw className="h-4 w-4 animate-spin" />
                  <span>Connecting to FastAPI backend...</span>
                </div>
              ) : responseOutput ? (
                <pre className="text-emerald-400 text-[11px] leading-relaxed select-all">
                  {JSON.stringify(responseOutput, null, 2)}
                </pre>
              ) : (
                <div className="text-slate-600 italic py-6 text-center">
                  Click 'Execute Request' to test this endpoint live
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
