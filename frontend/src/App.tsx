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
import { EmailHub } from './surfaces/EmailHub';
import type { EmailSeed } from './surfaces/EmailHub';
import { SECTION_LABEL } from './components/settings/sections';
import { BrowserDock } from './components/channels/BrowserDock';
import { ErrorBoundary } from './components/shared/ErrorBoundary';
import { apiFetch, getToken, clearToken, verifySession, UNAUTHORIZED_EVENT } from './lib/api';
import type { Me } from './lib/api';
import { useApi } from './lib/hooks';
import { useA11yLabels } from './lib/useA11yLabels';
import { useSidebarState } from './lib/useSidebarState';
import { useShortcuts } from './lib/useShortcuts';

const DEFAULT_SURFACES: Surface[] = ['today'];

const SURFACE_LABEL: Record<Surface, string> = {
  today: 'Today',
  find: 'Find',
  clients: 'Clients',
  channels: 'Channels',
  email: 'Email Hub',
  tools: 'Tools',
  settings: 'Settings',
};

export const ALLOWED_SURFACES: Record<string, Surface[]> = {
  super_admin: ['today', 'find', 'clients', 'channels', 'email', 'tools', 'settings'],
  growth_lead: ['today', 'find', 'clients', 'channels', 'email', 'tools'],
  sdr_rep: ['today', 'find', 'clients', 'channels', 'email', 'tools'],
  auditor: ['today', 'clients', 'email', 'tools'],
};

export function App() {
  const [me, setMe] = useState<Me | null>(null);
  const [checking, setChecking] = useState<boolean>(() => getToken() !== null);
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
  const [emailSeed, setEmailSeed] = useState<EmailSeed | null>(null);
  const inbox = useApi<{ count: number }>(me ? '/api/inbox' : null);
  useA11yLabels();

  // Restore a session for this tab, and return to sign-in whenever the API answers 401.
  useEffect(() => {
    const stored = getToken();
    if (!stored) {
      setChecking(false);
      return;
    }
    const timer = setTimeout(() => setChecking(false), 3000);
    verifySession(stored)
      .then((identity) => {
        clearTimeout(timer);
        if (identity) {
          setMe(identity);
        } else {
          clearToken();
        }
      })
      .catch(() => {
        clearTimeout(timer);
        clearToken();
      })
      .finally(() => setChecking(false));

    const onUnauthorized = () => {
      setMe(null);
      setAuthNotice('Your session ended. This happens after 12 hours or when the password of your tier is changed. Please sign in again.');
    };
    window.addEventListener(UNAUTHORIZED_EVENT, onUnauthorized);
    return () => {
      clearTimeout(timer);
      window.removeEventListener(UNAUTHORIZED_EVENT, onUnauthorized);
    };
  }, []);

  // Enforce role-based allowed surfaces whenever identity or surface changes
  useEffect(() => {
    if (!me) return;
    const allowed = ALLOWED_SURFACES[me.role] ?? DEFAULT_SURFACES;
    if (!allowed.includes(surface)) {
      setSurface('today');
    }
  }, [me, surface]);

  // Each screen has its own tab title, so history, bookmarks and screen readers can tell them apart
  useEffect(() => {
    document.title = me ? `${SURFACE_LABEL[surface]} | AgencyBD` : 'Sign in | AgencyBD';
  }, [me, surface]);

  // The stop-sending switch lives on the server, so it also stops scheduled sends.
  useEffect(() => {
    if (!me) return;
    apiFetch('/api/controls/outbound').then(async (r) => {
      if (r.ok) setHalted((await r.json()).halted);
    });
  }, [me]);

  const toggleHalt = async () => {
    const next = !halted;
    if (next && !window.confirm('Stop ALL sending for this workspace? Scheduled emails pause until you resume.')) return;
    const res = await apiFetch('/api/controls/outbound', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ halted: next, reason: next ? 'stopped from the header' : '' }),
    });
    if (res.ok) setHalted((await res.json()).halted);
    else window.alert('Your role may not change this switch.');
  };

  const allowedSurfaces: Surface[] = me ? (ALLOWED_SURFACES[me.role] ?? DEFAULT_SURFACES) : DEFAULT_SURFACES;

  const navigate = (s: Surface) => {
    if (allowedSurfaces.includes(s)) {
      setSurface(s);
    } else {
      setSurface('today');
    }
  };

  const fromPalette = (c: Command) => {
    if (allowedSurfaces.includes(c.surface)) {
      setSurface(c.surface);
      if (c.section) setSettingsSection(c.section);
    } else {
      setSurface('today');
    }
  };

  const openClient = (id: number) => {
    setSurface('clients');
    setOpenLead(id);
  };

  const openEmailComposer = (s: EmailSeed) => {
    if (!allowedSurfaces.includes('email')) {
      setSurface('today');
      return;
    }
    setEmailSeed(s);
    setSurface('email');
  };

  const fromText = (kind: 'find' | 'quicklog', text: string) => {
    const targetSurface = kind === 'find' ? 'find' : 'channels';
    if (!allowedSurfaces.includes(targetSurface)) {
      setSurface('today');
      return;
    }
    setSeed({ [kind]: text, n: Date.now() });
    setSurface(targetSurface);
  };

  const goSettings = (section = 'setup') => {
    if (!allowedSurfaces.includes('settings')) {
      setSurface('today');
      return;
    }
    setSettingsSection(section);
    setSurface('settings');
  };

  useShortcuts({
    enabled: !!me,
    onNavigate: navigate,
    onToggleSidebar: toggleCollapsed,
    onHelp: () => setHelpOpen((v) => !v),
    allowedSurfaces,
  });

  if (checking) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-slate-950">
        <div className="flex flex-col items-center gap-3">
          <div className="h-8 w-8 rounded-full border-2 border-indigo-500 border-t-transparent animate-spin" />
          <span className="text-xs text-slate-400 font-medium">Verifying secure session…</span>
        </div>
      </div>
    );
  }
  if (!me) return <AuthGate onAuthenticated={setMe} notice={authNotice} />;

  const crumbs = surface === 'settings' ? ['Settings', SECTION_LABEL[settingsSection] ?? 'Setup'] : [SURFACE_LABEL[surface]];

  return (
    <div className="min-h-screen text-slate-100 flex font-sans antialiased">
      <a
        href="#main"
        className="sr-only focus:not-sr-only focus:absolute focus:z-[70] focus:top-2 focus:left-2 focus:bg-indigo-600 focus:text-white focus:px-3 focus:py-2 focus:rounded-lg"
      >
        Skip to content
      </a>
      <Sidebar
        active={surface}
        onNavigate={navigate}
        badge={inbox.data?.count}
        collapsed={collapsed}
        onToggleCollapsed={toggleCollapsed}
        mobileMenuOpen={mobileMenuOpen}
        setMobileMenuOpen={setMobileMenuOpen}
        identity={me}
        onSignOut={() => {
          clearToken();
          setMe(null);
          setAuthNotice('');
        }}
        onPalette={() => setPaletteSignal((n) => n + 1)}
        onHelp={() => setHelpOpen(true)}
        onDock={() => setDockOpen(true)}
        halted={halted}
      />
      <div className="flex-1 min-w-0 flex flex-col">
        {halted && (
          <div role="alert" className="bg-rose-600 text-white text-xs text-center py-1.5 px-3">
            Sending is stopped for this workspace, including scheduled emails. Use Resume sending in the header to continue.
          </div>
        )}
        <Header
          halted={halted}
          onToggleHalt={toggleHalt}
          setMobileMenuOpen={setMobileMenuOpen}
          onPalette={() => setPaletteSignal((n) => n + 1)}
          crumbs={crumbs}
        />
        <main id="main" className="flex-1 min-w-0 p-4 sm:p-6 lg:p-8 pb-24 lg:pb-8 max-w-[1400px] w-full mx-auto">
          <ErrorBoundary fallbackTitle="Application Workspace Encountered an Issue" onReset={() => setSurface('today')}>
            <div key={surface} className="page-enter">
              {surface === 'today' && (
                <Today
                  identity={me}
                  onOpenClient={openClient}
                  onSettings={(section) => goSettings(section ?? 'setup')}
                  onGo={navigate}
                  onSearch={(q) => fromText('find', q)}
                  onSendEmail={openEmailComposer}
                />
              )}
              {surface === 'find' && allowedSurfaces.includes('find') && (
                <Find
                  onOpenClient={openClient}
                  onAddGoogleKey={() => goSettings('keys')}
                  seed={seed.find ? { text: seed.find, n: seed.n } : null}
                  onSendEmail={openEmailComposer}
                  identity={me}
                />
              )}
              {surface === 'clients' && (
                <Clients
                  openLead={openLead}
                  setOpenLead={setOpenLead}
                  identity={me}
                  onSendEmail={openEmailComposer}
                />
              )}
              {surface === 'channels' && allowedSurfaces.includes('channels') && (
                <Channels
                  active={channel}
                  onActive={setChannel}
                  quick={seed.quicklog ? { text: seed.quicklog, n: seed.n } : null}
                  onOpenAlerts={() => goSettings('alerts')}
                />
              )}
              {surface === 'email' && allowedSurfaces.includes('email') && (
                <EmailHub
                  identity={me}
                  seed={emailSeed}
                  onClearSeed={() => setEmailSeed(null)}
                  onOpenClient={openClient}
                />
              )}
              {surface === 'tools' && <Tools onOpenClient={openClient} />}
              {surface === 'settings' && allowedSurfaces.includes('settings') && (
                <Settings
                  me={me}
                  section={settingsSection}
                  setSection={setSettingsSection}
                  onSignOut={() => {
                    clearToken();
                    setMe(null);
                    setAuthNotice('');
                  }}
                />
              )}
            </div>
          </ErrorBoundary>
        </main>
      </div>
      <MobileTabBar active={surface} onNavigate={navigate} badge={inbox.data?.count} identity={me} />
      <CommandPalette
        onNavigate={fromPalette}
        onText={fromText}
        openSignal={paletteSignal}
        allowedSurfaces={allowedSurfaces}
      />
      <BrowserDock
        open={dockOpen}
        onClose={() => setDockOpen(false)}
        onChannel={(id) => {
          setChannel(id);
          setSurface('channels');
        }}
      />
      <ShortcutsHelp open={helpOpen} onClose={() => setHelpOpen(false)} />
    </div>
  );
}

export default App;
