import type { FC } from 'react';
import { Radio, RefreshCw, Search, Users, Wrench } from 'lucide-react';
import { FollowupsPanel } from '../components/clients/FollowupsPanel';
import { Button, Card, EmptyState, PageHeader, Skeletons } from '../components/ui';
import { ErrorBanner } from '../components/shared/ErrorBanner';
import { DigestPanel } from '../components/shared/DigestPanel';
import { TodayOverview } from '../components/today/TodayOverview';
import type { Surface } from '../types';
import { DiscoveryPanel } from '../components/today/DiscoveryPanel';
import { InboxItem } from '../components/today/InboxItem';
import type { InboxEntry } from '../components/today/InboxItem';
import { useApi } from '../lib/hooks';

interface Inbox { count: number; items: InboxEntry[] }

export const Today: FC<{ onOpenClient: (leadId: number) => void; onSettings: (section?: string) => void; onGo: (s: Surface) => void }> = ({ onOpenClient, onSettings, onGo }) => {
  const inbox = useApi<Inbox>('/api/inbox');
  const items = inbox.data?.items ?? [];

  return (
    <div className="space-y-5">
      <PageHeader
        title="Today"
        subtitle="What needs you, in order. Everything else runs on its own and stops when it would otherwise have to guess."
        actions={<Button small onClick={inbox.reload}><RefreshCw className={`h-3.5 w-3.5 ${inbox.loading ? 'animate-spin' : ''}`} />Refresh</Button>}
      />
      <TodayOverview onGo={(surface, opts) => {
        if (opts?.leadId) onOpenClient(opts.leadId);
        else if (surface === 'settings') onSettings(opts?.section);
        else if (surface !== 'today') onGo(surface);
      }} />
      <div className="flex flex-wrap gap-2" aria-label="Quick actions">
        <Button small onClick={() => onGo('find')}><Search className="h-3.5 w-3.5" />Find prospects</Button>
        <Button small onClick={() => onGo('clients')}><Users className="h-3.5 w-3.5" />Open clients</Button>
        <Button small onClick={() => onGo('channels')}><Radio className="h-3.5 w-3.5" />Channels</Button>
        <Button small onClick={() => onGo('tools')}><Wrench className="h-3.5 w-3.5" />Tools</Button>
      </div>
      <FollowupsPanel onOpenClient={onOpenClient} />

      <DiscoveryPanel onDone={inbox.reload} onOpenClient={onOpenClient} />

      <Card>
        <h2 className="text-sm font-semibold text-white mb-1">Your inbox</h2>
        <ErrorBanner message={inbox.error} />
        {inbox.loading && !inbox.data ? <Skeletons rows={3} /> : items.length === 0 && !inbox.error ? (
          <EmptyState title="You're all caught up" hint="Run a search above to find prospects. Drafts and tasks will appear here." />
        ) : (
          <ul className="divide-y divide-slate-800">
            {items.map((i) => <InboxItem key={`${i.type}-${i.id}`} item={i} onChanged={inbox.reload} onOpenClient={onOpenClient} onSettings={onSettings} />)}
          </ul>
        )}
      </Card>

      <DigestPanel />
    </div>
  );
};
