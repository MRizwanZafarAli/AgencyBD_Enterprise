import { useEffect, useState } from 'react';
import type { TabType } from './types';
import { Header } from './components/layout/Header';
import { Sidebar } from './components/layout/Sidebar';
import { AuthGate } from './components/layout/AuthGate';
import { CommandPalette } from './components/layout/CommandPalette';
import { LocalHunt } from './components/modules/LocalHunt';
import { apiFetch, getApiKey, clearApiKey, verifyKey, UNAUTHORIZED_EVENT } from './lib/api';
import type { Me } from './lib/api';

// Modular Modules
import { MissionControl } from './components/modules/MissionControl';
import { WebsiteDoctor } from './components/modules/WebsiteDoctor';
import { OpportunityRadar } from './components/modules/OpportunityRadar';
import { PortfolioManager } from './components/modules/PortfolioManager';
import { SequencesManager } from './components/modules/SequencesManager';
import { OpenSourcing } from './components/modules/OpenSourcing';
import { WaterfallEnrich } from './components/modules/WaterfallEnrich';
import { FleetRouter } from './components/modules/FleetRouter';
import { CopyCoach } from './components/modules/CopyCoach';
import { CallIntel } from './components/modules/CallIntel';
import { MultimodalStudio } from './components/modules/MultimodalStudio';
import { DnsStudio } from './components/modules/DnsStudio';
import { CanSpamVault } from './components/modules/CanSpamVault';
import { EnterpriseRbac } from './components/modules/EnterpriseRbac';
import { ApiExplorer } from './components/modules/ApiExplorer';
import { GovernanceAndLearning } from './components/modules/GovernanceAndLearning';


export function App() {
  const [me, setMe] = useState<Me | null>(null);
  const [checking, setCheckingAuth] = useState<boolean>(() => getApiKey() !== null);
  const [authNotice, setAuthNotice] = useState('');

  // Restore a session for this tab, and drop back to the sign-in screen whenever the API answers 401.
  useEffect(() => {
    const stored = getApiKey();
    if (stored) {
      verifyKey(stored)
        .then((identity) => {
          if (identity) setMe(identity);
          else clearApiKey();
        })
        .catch(() => undefined)
        .finally(() => setCheckingAuth(false));
    }
    const onUnauthorized = () => {
      setMe(null);
      setAuthNotice('Your session expired or the key was revoked. Please sign in again.');
    };
    window.addEventListener(UNAUTHORIZED_EVENT, onUnauthorized);
    return () => window.removeEventListener(UNAUTHORIZED_EVENT, onUnauthorized);
  }, []);

  const signOut = () => {
    clearApiKey();
    setMe(null);
    setAuthNotice('');
  };

  const [activeTab, setActiveTab] = useState<TabType>('overview');
  const [circuitBreakerTripped, setCircuitBreakerTripped] = useState(false);

  // The kill switch lives on the server so it also stops scheduled sends.
  useEffect(() => {
    if (!me) return;
    apiFetch('/api/controls/outbound').then(async (r) => {
      if (r.ok) setCircuitBreakerTripped((await r.json()).halted);
    });
  }, [me]);

  const toggleHalt = async () => {
    const next = !circuitBreakerTripped;
    if (next && !window.confirm('Halt ALL outbound sending for this workspace? Scheduled sequences pause until you resume.')) return;
    const res = await apiFetch('/api/controls/outbound', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ halted: next, reason: next ? 'halted from the dashboard' : '' }),
    });
    if (res.ok) setCircuitBreakerTripped((await res.json()).halted);
    else window.alert('Could not change the kill switch: your role may not allow it.');
  };
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  // Cross-Module Seamless Bridge State
  const [waterfallBridgeData, setWaterfallBridgeData] = useState<{
    first: string;
    last: string;
    company: string;
    domain: string;
  }>({ first: '', last: '', company: '', domain: '' });

  const [copyCoachBridgeData, setCopyCoachBridgeData] = useState<{
    subject: string;
    body: string;
  }>({ subject: '', body: '' });

  // 1-Click Bridge Handlers (Zero Manual Typing)
  const handleBridgeToWaterfall = (first: string, last: string, company: string, domain: string) => {
    setWaterfallBridgeData({ first, last, company, domain });
    setActiveTab('waterfall');
  };

  const handleBridgeToCopyCoach = (first: string, company: string, domain: string) => {
    setCopyCoachBridgeData({
      subject: `quick question regarding ${company.toLowerCase()} engineering`,
      body: `Hi ${first},\n\nI looked at ${domain} and noted a few specific things worth a conversation (replace this line with a finding from your Website Doctor audit).\n\nOpen to a short call?`
    });
    setActiveTab('copycoach');
  };

  if (checking) return <div className="min-h-screen bg-slate-950" />;
  if (!me) return <AuthGate onAuthenticated={setMe} notice={authNotice} />;

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col font-sans selection:bg-indigo-500/30 selection:text-white antialiased">
      {/* 1. Header with Telemetry & Global Controls */}
      <Header
        circuitBreakerTripped={circuitBreakerTripped}
        onToggleHalt={toggleHalt}
        mobileMenuOpen={mobileMenuOpen}
        setMobileMenuOpen={setMobileMenuOpen}
        identity={me}
        onSignOut={signOut}
      />

      {/* 2. Main Body: Sidebar + Active Module Canvas */}
      <div className="flex-1 flex overflow-hidden">
        {/* Responsive Sidebar */}
        <Sidebar
          activeTab={activeTab}
          setActiveTab={setActiveTab}
          mobileMenuOpen={mobileMenuOpen}
          setMobileMenuOpen={setMobileMenuOpen}
        />

        {/* Content Viewport */}
        <main className="flex-1 overflow-y-auto p-4 sm:p-6 lg:p-8 max-w-7xl mx-auto w-full transition-all">
          <div key={activeTab} className="page-enter">
          {activeTab === 'hunt' && <LocalHunt />}
          {activeTab === 'overview' && (
            <MissionControl
              circuitBreakerTripped={circuitBreakerTripped}
              setActiveTab={setActiveTab}
            />
          )}

          {activeTab === 'doctor' && <WebsiteDoctor />}

          {activeTab === 'radar' && <OpportunityRadar />}
          {activeTab === 'portfolio' && <PortfolioManager />}
          {activeTab === 'sequences' && <SequencesManager />}

          {activeTab === 'governance' && <GovernanceAndLearning />}

          {activeTab === 'sourcing' && (

            <OpenSourcing
              onBridgeToWaterfall={handleBridgeToWaterfall}
              setActiveTab={setActiveTab}
            />
          )}

          {activeTab === 'waterfall' && (
            <WaterfallEnrich
              initialFirst={waterfallBridgeData.first}
              initialLast={waterfallBridgeData.last}
              initialCompany={waterfallBridgeData.company}
              initialDomain={waterfallBridgeData.domain}
              onBridgeToCopyCoach={handleBridgeToCopyCoach}
              setActiveTab={setActiveTab}
            />
          )}

          {activeTab === 'deliverability' && <FleetRouter />}

          {activeTab === 'copycoach' && (
            <CopyCoach
              initialSubject={copyCoachBridgeData.subject}
              initialBody={copyCoachBridgeData.body}
            />
          )}

          {activeTab === 'callintel' && <CallIntel />}

          {activeTab === 'multimodal' && <MultimodalStudio />}

          {activeTab === 'dns' && <DnsStudio />}

          {activeTab === 'suppression' && <CanSpamVault />}

          {activeTab === 'rbac' && <EnterpriseRbac selectedTenant={me.org_id} />}

          {activeTab === 'apidocs' && <ApiExplorer />}
          </div>
        </main>
      </div>
      <CommandPalette onNavigate={setActiveTab} />
    </div>
  );
}

export default App;
