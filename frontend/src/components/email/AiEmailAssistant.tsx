import { useState } from 'react';
import type { FC } from 'react';
import { Check, ClipboardCopy, Cpu, Sparkles, Wand2 } from 'lucide-react';
import { Badge, Button, field } from '../ui';
import { apiFetch, apiErrorMessage } from '../../lib/api';

type Provider = 'auto' | 'ollama' | 'openai' | 'anthropic' | 'gemini' | 'openai_compatible' | 'manual';

const PROVIDER_OPTIONS: Array<{ id: Provider; label: string; defaultModel: string; defaultUrl?: string }> = [
  { id: 'auto', label: 'Auto (Server Key / Fallback)', defaultModel: '' },
  { id: 'ollama', label: 'Ollama (Local AI)', defaultModel: 'llama3.1', defaultUrl: 'http://localhost:11434' },
  { id: 'openai_compatible', label: 'Local / Custom OpenAI-Compatible (LM Studio, Groq, OpenRouter)', defaultModel: 'local-model', defaultUrl: 'http://localhost:1234/v1' },
  { id: 'openai', label: 'OpenAI (Paid API)', defaultModel: 'gpt-4o-mini', defaultUrl: 'https://api.openai.com/v1' },
  { id: 'anthropic', label: 'Anthropic Claude (Paid API)', defaultModel: 'claude-3-5-sonnet-latest' },
  { id: 'gemini', label: 'Google Gemini (Paid API)', defaultModel: 'gemini-2.0-flash' },
  { id: 'manual', label: 'Manual Copy-Paste (ChatGPT / Claude / Any AI)', defaultModel: '' },
];

const STORE_KEY = 'agencybd.ai_writer.prefs';

function loadPrefs(): { provider: Provider; model: string; baseUrl: string } {
  try {
    const raw = JSON.parse(localStorage.getItem(STORE_KEY) ?? '{}');
    return {
      provider: raw.provider || 'auto',
      model: raw.model || '',
      baseUrl: raw.baseUrl || '',
    };
  } catch {
    return { provider: 'auto', model: '', baseUrl: '' };
  }
}

export const AiEmailAssistant: FC<{
  recipientName: string;
  companyName: string;
  onApply: (draft: { subject: string; body: string }) => void;
}> = ({ recipientName, companyName, onApply }) => {
  const initial = loadPrefs();
  const [provider, setProvider] = useState<Provider>(initial.provider);
  const [model, setModel] = useState(initial.model);
  const [baseUrl, setBaseUrl] = useState(initial.baseUrl);
  const [apiKey, setApiKey] = useState('');
  const [tone, setTone] = useState('consultative');
  const [goal, setGoal] = useState('');
  const [context, setContext] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [status, setStatus] = useState('');
  const [copiedPrompt, setCopiedPrompt] = useState(false);
  const [manualPaste, setManualPaste] = useState('');

  const savePrefs = (p: Provider, m: string, u: string) => {
    try {
      localStorage.setItem(STORE_KEY, JSON.stringify({ provider: p, model: m, baseUrl: u }));
    } catch { /* ignore storage errors */ }
  };

  const onProviderChange = (next: Provider) => {
    const cfg = PROVIDER_OPTIONS.find((x) => x.id === next);
    const nextModel = cfg?.defaultModel ?? '';
    const nextUrl = cfg?.defaultUrl ?? '';
    setProvider(next);
    setModel(nextModel);
    setBaseUrl(nextUrl);
    savePrefs(next, nextModel, nextUrl);
    setError('');
    setStatus('');
  };

  const promptText = [
    'Write a concise, human B2B outreach email (under 130 words, zero hype).',
    `Recipient: ${recipientName || 'Decision Maker'}`,
    `Company: ${companyName || 'Prospect Company'}`,
    `Tone: ${tone}`,
    goal ? `Goal / Offer: ${goal}` : '',
    context ? `Context: ${context}` : '',
    'Format strictly as:',
    'Subject: <one crisp subject line>',
    '',
    '<email body>',
  ].filter(Boolean).join('\n');

  const copyPrompt = async () => {
    try {
      await navigator.clipboard.writeText(promptText);
      setCopiedPrompt(true);
      window.setTimeout(() => setCopiedPrompt(false), 1800);
    } catch {
      setCopiedPrompt(false);
    }
  };

  const parseAndApplyManual = () => {
    const raw = manualPaste.trim();
    if (!raw) return;
    const lines = raw.split(/\r?\n/);
    let subj = companyName ? `Quick idea for ${companyName}` : 'Quick question';
    let startIdx = 0;
    for (let i = 0; i < Math.min(4, lines.length); i++) {
      const m = lines[i].match(/^\s*(?:Subject|SUBJ)\s*:\s*(.+)$/i);
      if (m) {
        subj = m[1].trim().replace(/^["']|["']$/g, '');
        startIdx = i + 1;
        break;
      }
    }
    const bdy = lines.slice(startIdx).join('\n').trim() || raw;
    onApply({ subject: subj, body: bdy });
    setStatus('Applied pasted AI draft to Subject & Body.');
  };

  const generateWithApi = async () => {
    setLoading(true);
    setError('');
    setStatus('');
    savePrefs(provider, model, baseUrl);
    try {
      const res = await apiFetch('/api/email/ai-draft', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          provider,
          model: model.trim() || undefined,
          base_url: baseUrl.trim() || undefined,
          api_key: apiKey.trim() || undefined,
          recipient_name: recipientName,
          company_name: companyName,
          goal,
          tone,
          context,
        }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(apiErrorMessage(res.status, data));
      onApply({ subject: data.subject, body: data.body });
      setStatus(`Drafted via ${data.provider_used} (${data.model_used}).`);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  };

  const needsUrl = provider === 'ollama' || provider === 'openai_compatible' || provider === 'openai';
  const needsKey = provider === 'openai' || provider === 'anthropic' || provider === 'gemini' || provider === 'openai_compatible';

  return (
    <div className="rounded-xl border border-indigo-500/30 bg-slate-950/70 p-4 space-y-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <Cpu className="h-4 w-4 text-indigo-400" />
          <span className="text-xs font-semibold text-white">AI Email Writer (Local, Paid, or Manual Copy-Paste)</span>
        </div>
        <Badge tone="accent">{provider === 'manual' ? 'Copy-Paste Mode' : provider}</Badge>
      </div>

      <div className="grid gap-2 sm:grid-cols-2">
        <label className="text-[11px] text-slate-400 space-y-1">
          AI Provider
          <select className={field} value={provider} onChange={(e) => onProviderChange(e.target.value as Provider)}>
            {PROVIDER_OPTIONS.map((p) => (
              <option key={p.id} value={p.id}>{p.label}</option>
            ))}
          </select>
        </label>
        <label className="text-[11px] text-slate-400 space-y-1">
          Tone
          <select className={field} value={tone} onChange={(e) => setTone(e.target.value)}>
            <option value="consultative">Consultative & Direct</option>
            <option value="executive">Executive Brief</option>
            <option value="friendly">Warm & Conversational</option>
            <option value="technical">Technical Teardown</option>
          </select>
        </label>
      </div>

      {provider !== 'manual' && provider !== 'auto' && (
        <div className="grid gap-2 sm:grid-cols-3">
          <input className={field} placeholder="Model (e.g. llama3.1, gpt-4o-mini)" value={model} onChange={(e) => setModel(e.target.value)} />
          {needsUrl && (
            <input className={field} placeholder="Base URL (e.g. http://localhost:11434)" value={baseUrl} onChange={(e) => setBaseUrl(e.target.value)} />
          )}
          {needsKey && (
            <input className={field} type="password" placeholder="API Key (optional if set on server)" value={apiKey} onChange={(e) => setApiKey(e.target.value)} />
          )}
        </div>
      )}

      <div className="grid gap-2 sm:grid-cols-2">
        <input className={field} placeholder="Goal / offer (e.g. 15-min speed & SEO audit call)" value={goal} onChange={(e) => setGoal(e.target.value)} />
        <input className={field} placeholder="Account context (e.g. hiring React devs, slow LCP)" value={context} onChange={(e) => setContext(e.target.value)} />
      </div>

      {provider === 'manual' ? (
        <div className="space-y-2 pt-1">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <span className="text-[11px] text-slate-400">1. Copy prompt to ChatGPT, Claude, or Local AI → 2. Paste output below</span>
            <Button small type="button" onClick={copyPrompt}>
              {copiedPrompt ? <Check className="h-3.5 w-3.5 text-emerald-400" /> : <ClipboardCopy className="h-3.5 w-3.5" />}
              {copiedPrompt ? 'Prompt Copied' : 'Copy AI Prompt'}
            </Button>
          </div>
          <textarea
            className={field}
            rows={4}
            placeholder={'Paste AI output here (supports "Subject: ..." on first line + body)...'}
            value={manualPaste}
            onChange={(e) => setManualPaste(e.target.value)}
          />
          <Button small type="button" variant="primary" disabled={!manualPaste.trim()} onClick={parseAndApplyManual}>
            <Wand2 className="h-3.5 w-3.5" /> Apply Pasted Draft to Composer
          </Button>
        </div>
      ) : (
        <div className="flex flex-wrap items-center gap-2">
          <Button small type="button" variant="primary" disabled={loading} onClick={generateWithApi}>
            <Sparkles className="h-3.5 w-3.5" />
            {loading ? 'Generating…' : 'Generate Email Draft'}
          </Button>
          <Button small type="button" onClick={copyPrompt}>
            {copiedPrompt ? <Check className="h-3.5 w-3.5 text-emerald-400" /> : <ClipboardCopy className="h-3.5 w-3.5" />}
            {copiedPrompt ? 'Prompt Copied' : 'Copy Prompt Instead'}
          </Button>
        </div>
      )}

      {status && <p className="text-[11px] text-emerald-400">{status}</p>}
      {error && <p className="text-[11px] text-rose-400">{error}</p>}
    </div>
  );
};
