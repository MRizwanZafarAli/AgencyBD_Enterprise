import { useEffect, useState } from 'react';
import type { Surface } from './types';
import { Header } from './components/layout/Header';
import { Sidebar, MobileTabBar } from './components/layout/Sidebar';
import { ShortcutsHelp } from './components/layout/ShortcutsHelp';
import { AuthGate } from './components/layout/AuthGate';
import { CommandPalette } from './components/layout/CommandPalette';
import type { Command } from './components/layout/commands';
import { Today } from './surfaces/Today';
import { Find } from './surfaces/Find';
import { Clients } from './surfaces/Clients';
import { Settings } from './surfaces/Settings';
import { Tools } from './surfaces/Tools';
import { Channels } from './surfaces/Channels';
import { SECTION_LABEL } from './components/settings/sections';
import { BrowserDock } from './components/channels/BrowserDock';
import { apiFetch, getApiKey, clearApiKey, verifyKey, UNAUTHORIZED_EVENT } from './lib/api';
import type { Me } from './lib/api';
import { useApi } from './lib/hooks';
import { useA11yLabels } from './lib/useA11yLabels';
import { useSidebarState } from './lib/useSidebarState';
import { useShortcuts } from './lib/useShortcuts';

export function App() {
  const [me, setMe] = useState<Me | null>(null);
  const [checking, setChecking] = useState<boolean>(() => getApiKey() !== null);
  const [authNotice, setAuthNotice] = useState('');
  const [surface, setSurface] = useState<Surface>('today');
  const [settingsSection, setSettingsSection] = useState('setup');
  const [openLead, setOpenLead] = useState<number | null>(null);
  const [halted, setHalted] = useState(false);
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const [paletteSignal, setPaletteSignal] = useState(0);
  const [collapsed, toggleCollapsed] = useSidebarState();
  const [helpOpen, setHelpOpen] = useState(false);
  const [dockOpen, setDockOpen] = useState(false);
  const [channel, setChannel] = useState('linkedin');
  const [seed, setSeed] = useState<{ find?: string; quicklog?: string; n: number }>({ n: 0 });
  const inbox = useApi<{ count: number }>(me ? '/api/inbox' : null);
  useA11yLabels();

  // Restore a session for this tab, and return to sign-in whenever the API answers 401.
  useEffect(() => {
    const stored = getApiKey();
    if (stored) {
      verifyKey(stored).then((identity) => (identity ? setMe(identity) : clearApiKey())).catch(() => undefined).finally(() => setChecking(false));
    }
    const onUnauthorized = () => { setMe(null); setAuthNotice('Your session expired or the key was revoked. Please sign in again.'); };
    window.addEventListener(UNAUTHORIZED_EVENT, onUnauthorized);
    return () => window.removeEventListener(UNAUTHORIZED_EVENT, onUnauthorized);
  }, []);

  // The stop-sending switch lives on the server, so it also stops scheduled sends.
  useEffect(() => {
    if (!me) return;
    apiFetch('/api/controls/outbound').then(async (r) => { if (r.ok) setHalted((await r.json()).halted); });
  }, [me]);

  const toggleHalt = async () => {
    const next = !halted;
    if (next && !window.confirm('Stop ALL sending for this workspace? Scheduled emails pause until you resume.')) return;
    const res = await apiFetch('/api/controls/outbound', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ halted: next, reason: next ? 'stopped from the header' : '' }) });
    if (res.ok) setHalted((await res.json()).halted); else window.alert('Your role may not change this switch.');
  };

  const navigate = (s: Surface) => setSurface(s);
  const fromPalette = (c: Command) => { setSurface(c.surface); if (c.section) setSettingsSection(c.section); };
  const openClient = (id: number) => { setSurface('clients'); setOpenLead(id); };
  const fromText = (kind: 'find' | 'quicklog', text: string) => { setSeed({ [kind]: text, n: Date.now() }); setSurface(kind === 'find' ? 'find' : 'channels'); };
  const goSettings = (section = 'setup') => { setSettingsSection(section); setSurface('settings'); };

  useShortcuts({ enabled: !!me, onNavigate: setSurface, onToggleSidebar: toggleCollapsed, onHelp: () => setHelpOpen((v) => !v) });

  if (checking) return <div className="min-h-screen" />;
  if (!me) return <AuthGate onAuthenticated={setMe} notice={authNotice} />;

  const SURFACE_LABEL: Record<Surface, string> = { today: 'Today', find: 'Find', clients: 'Clients', channels: 'Channels', tools: 'Tools', settings: 'Settings' };
  const crumbs = surface === 'settings' ? ['Settings', SECTION_LABEL[settingsSection] ?? 'Setup'] : [SURFACE_LABEL[surface]];

  return (
    <div className="min-h-screen text-slate-100 flex font-sans antialiased">
      <a href="#main" className="sr-only focus:not-sr-only focus:absolute focus:z-[70] focus:top-2 focus:left-2 focus:bg-indigo-600 focus:text-white focus:px-3 focus:py-2 focus:rounded-lg">Skip to content</a>
      <Sidebar active={surface} onNavigate={navigate} badge={inbox.data?.count} collapsed={collapsed} onToggleCollapsed={toggleCollapsed} mobileMenuOpen={mobileMenuOpen}
        setMobileMenuOpen={setMobileMenuOpen} identity={me} onSignOut={() => { clearApiKey(); setMe(null); setAuthNotice(''); }} onPalette={() => setPaletteSignal((n) => n + 1)} onHelp={() => setHelpOpen(true)} onDock={() => setDockOpen(true)} halted={halted} />
      <div className="flex-1 min-w-0 flex flex-col">
        {halted && <div role="alert" className="bg-rose-600 text-white text-xs text-center py-1.5 px-3">Sending is stopped for this workspace, including scheduled emails. Use Resume sending in the header to continue.</div>}
        <Header halted={halted} onToggleHalt={toggleHalt} setMobileMenuOpen={setMobileMenuOpen} onPalette={() => setPaletteSignal((n) => n + 1)} crumbs={crumbs} />
        <main id="main" className="flex-1 min-w-0 p-4 sm:p-6 lg:p-8 pb-24 lg:pb-8 max-w-[1400px] w-full mx-auto">
          <div key={surface} className="page-enter">
            {surface === 'today' && <Today onOpenClient={openClient} onSettings={(section) => goSettings(section ?? 'setup')} onGo={navigate} />}
            {surface === 'find' && <Find onOpenClient={openClient} onAddGoogleKey={() => goSettings('keys')} seed={seed.find ? { text: seed.find, n: seed.n } : null} />}
            {surface === 'clients' && <Clients openLead={openLead} setOpenLead={setOpenLead} />}
            {surface === 'channels' && <Channels active={channel} onActive={setChannel} quick={seed.quicklog ? { text: seed.quicklog, n: seed.n } : null} onOpenAlerts={() => goSettings('alerts')} />}
            {surface === 'tools' && <Tools onOpenClient={openClient} />}
            {surface === 'settings' && <Settings me={me} section={settingsSection} setSection={setSettingsSection} onSignOut={() => { clearApiKey(); setMe(null); setAuthNotice(''); }} />}
          </div>
        </main>
      </div>
      <MobileTabBar active={surface} onNavigate={navigate} badge={inbox.data?.count} />
      <CommandPalette onNavigate={fromPalette} onText={fromText} openSignal={paletteSignal} />
      <BrowserDock open={dockOpen} onClose={() => setDockOpen(false)} onChannel={(id) => { setChannel(id); setSurface('channels'); }} />
      <ShortcutsHelp open={helpOpen} onClose={() => setHelpOpen(false)} />
    </div>
  );
}

export default App;
