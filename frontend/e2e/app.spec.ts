import { test, expect } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';
import type { Page } from '@playwright/test';

const PASSWORDS: Record<string, string> = JSON.parse(process.env.E2E_PASSWORDS ?? '{}');
const PASSWORD = PASSWORDS.super_admin ?? '';
const SURFACES = ['Today', 'Find', 'Clients', 'Channels', 'Tools', 'Settings'];
const TIER_LABEL: Record<string, string> = { super_admin: 'Super admin', growth_lead: 'Growth lead', sdr_rep: 'Sales rep', auditor: 'Auditor' };

async function signInAs(page: Page, role: string) {
  await page.goto('/');
  await page.getByLabel('Tier').selectOption(role);
  await page.getByLabel('Password', { exact: true }).fill(PASSWORDS[role]);
  await page.getByRole('button', { name: 'Sign in' }).click();
  await expect(page.locator('#main')).toBeVisible();
}
const signIn = (page: Page) => signInAs(page, 'super_admin');

/** A session token for direct API calls in tests (sign in over HTTP, exactly as the screen does). */
async function sessionHeaders(request: import('@playwright/test').APIRequestContext) {
  const r = await request.post('/api/auth/login', { data: { role: 'super_admin', password: PASSWORD } });
  return { Authorization: `Bearer ${(await r.json()).token}` };
}

test.beforeAll(() => { if (!PASSWORD) throw new Error('E2E_PASSWORDS is required (scripts/e2e.sh sets it)'); });

test('a wrong password is refused plainly, and no password is shipped in the page source', async ({ page, request }) => {
  await page.goto('/');
  await page.getByLabel('Password', { exact: true }).fill('definitely-not-the-password-1');
  await page.getByRole('button', { name: 'Sign in' }).click();
  await expect(page.getByRole('alert').filter({ hasText: 'That tier and password do not match.' })).toBeVisible();
  await expect(page.getByRole('navigation', { name: 'Main' })).toHaveCount(0);
  const html = await (await request.get('/')).text();
  const bundles = [...html.matchAll(/assets\/[^"']+\.js/g)].map((m) => m[0]);
  for (const b of bundles) {
    const code = await (await request.get('/' + b)).text();
    for (const pw of Object.values(PASSWORDS)) expect(code).not.toContain(pw);
    expect(code).not.toMatch(/agy_live_[0-9a-f]{32,}/);
  }
});

test('sign-in: the tier list, the show and hide button, and that the password box hides what you type', async ({ page }) => {
  await page.goto('/');
  const tier = page.getByLabel('Tier');
  await expect(tier.locator('option')).toHaveText(['Super admin', 'Growth lead', 'Sales rep', 'Auditor']);
  const box = page.getByLabel('Password', { exact: true });
  await box.fill('typed-secret');
  await expect(box).toHaveAttribute('type', 'password');
  await page.getByRole('button', { name: 'Show password' }).click();
  await expect(box).toHaveAttribute('type', 'text');
  await page.getByRole('button', { name: 'Hide password' }).click();
  await expect(box).toHaveAttribute('type', 'password');
  await expect(page.getByRole('button', { name: 'Sign in' })).toBeEnabled();
});

for (const [role, hidden] of [['growth_lead', ['Settings']], ['sdr_rep', ['Settings']], ['auditor', ['Find', 'Channels', 'Settings']]] as Array<[string, string[]]>) {
  test(`each tier gets its own screens: ${TIER_LABEL[role]} signs in with its own password`, async ({ page }) => {
    await signInAs(page, role);
    const nav = page.getByRole('navigation', { name: 'Main' });
    await expect(nav.getByRole('button', { name: /^Today/ })).toBeVisible();
    for (const h of hidden) await expect(nav.getByRole('button', { name: new RegExp(`^${h}`) })).toHaveCount(0);
  });
}

test('one tier password does not open another tier', async ({ page }) => {
  await page.goto('/');
  await page.getByLabel('Tier').selectOption('super_admin');
  await page.getByLabel('Password', { exact: true }).fill(PASSWORDS.auditor);
  await page.getByRole('button', { name: 'Sign in' }).click();
  await expect(page.getByRole('alert').filter({ hasText: 'do not match' })).toBeVisible();
  await expect(page.getByRole('navigation', { name: 'Main' })).toHaveCount(0);
});

test('access and passwords: the super admin changes a tier password, the old one stops working, and it is changed back', async ({ page }) => {
  await signIn(page);
  await page.getByRole('navigation', { name: 'Main' }).getByRole('button', { name: /^Settings/ }).click();
  await page.getByRole('navigation', { name: 'Settings sections' }).getByRole('button', { name: 'Access and passwords' }).click();
  await expect(page.getByRole('heading', { name: 'Tier passwords' })).toBeVisible();
  await expect(page.getByText('Password set')).toHaveCount(4);
  const fresh = 'Brand-New_Phrase-Of-Seven7!';
  await page.getByRole('button', { name: 'Change password for Auditor' }).click();
  await page.getByLabel('New password').fill('aaaaaaaaaaaaaaaa');
  await page.getByLabel('Type it again').fill('aaaaaaaaaaaaaaaa');
  await page.getByRole('button', { name: 'Save password' }).click();
  await expect(page.getByRole('alert')).toBeVisible();                                              // too repetitive: refused with a reason
  await page.getByLabel('New password').fill(PASSWORDS.growth_lead);
  await page.getByLabel('Type it again').fill(PASSWORDS.growth_lead);
  await page.getByRole('button', { name: 'Save password' }).click();
  await expect(page.getByRole('alert').filter({ hasText: 'Another tier already uses this password' })).toBeVisible();
  await page.getByLabel('New password').fill(fresh);
  await page.getByLabel('Type it again').fill(fresh);
  await page.getByRole('button', { name: 'Save password' }).click();
  await expect(page.getByRole('status').filter({ hasText: /Password for Auditor changed/ })).toBeVisible();

  const old = await page.request.post('/api/auth/login', { data: { role: 'auditor', password: PASSWORDS.auditor } });
  expect(old.status()).toBe(401);
  expect((await page.request.post('/api/auth/login', { data: { role: 'auditor', password: fresh } })).status()).toBe(200);

  await page.getByRole('button', { name: 'Change password for Auditor' }).click();                  // put it back so the other tests still work
  await page.getByLabel('New password').fill(PASSWORDS.auditor);
  await page.getByLabel('Type it again').fill(PASSWORDS.auditor);
  await page.getByRole('button', { name: 'Save password' }).click();
  await expect(page.getByRole('status').filter({ hasText: /Password for Auditor changed/ })).toBeVisible();
});

test('four surfaces, command palette and no console errors anywhere', async ({ page }) => {
  const problems: string[] = [];
  page.on('console', (m) => m.type() === 'error' && problems.push(m.text()));
  page.on('pageerror', (e) => problems.push(String(e)));
  page.on('response', (r) => r.status() >= 400 && r.status() !== 401 && problems.push(`${r.status()} ${r.url()}`));
  await signIn(page);
  for (const s of SURFACES) {
    await page.getByRole('navigation', { name: 'Main' }).getByRole('button', { name: new RegExp(`^${s}`) }).click();
    // Today's page title is the dashboard of the signed-in tier (for example "Workspace Operations & Governance"), so only its presence is checked there
    await expect((s === 'Today' ? page.getByRole('heading', { level: 1 }).first() : page.getByRole('heading', { level: 1, name: s }))).toBeVisible();
  }
  for (const section of ['Setup', 'Services and proof', 'Sending and policy', 'Domain DNS', 'Unsubscribe list', 'Access and passwords', 'Developer', 'How it works']) {
    await page.getByRole('navigation', { name: 'Settings sections' }).getByRole('button', { name: section }).click();
    await page.waitForTimeout(400);
  }
  await page.keyboard.press('Control+k');
  await page.getByLabel('Go to').fill('local');
  await page.keyboard.press('Enter');
  await expect(page.getByRole('heading', { level: 1, name: 'Find' })).toBeVisible();
  expect(problems, problems.join('\n')).toEqual([]);
});

test('accessibility: no serious or critical axe violations on the four surfaces', async ({ page }) => {
  await signIn(page);
  for (const s of SURFACES) {
    await page.getByRole('navigation', { name: 'Main' }).getByRole('button', { name: new RegExp(`^${s}`) }).click();
    await page.waitForTimeout(700);
    const results = await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa']).analyze();
    const bad = results.violations.filter((v) => v.impact === 'serious' || v.impact === 'critical');
    expect(bad.map((v) => `${s}: ${v.id} (${v.nodes.length}) ${v.help}`), `axe on ${s}`).toEqual([]);
  }
});

test('stop-sending switch halts the workspace and resumes it', async ({ page }) => {
  await signIn(page);
  page.on('dialog', (d) => d.accept());
  await page.getByRole('button', { name: /Stop sending/ }).click();
  await expect(page.getByRole('alert').filter({ hasText: 'Sending is stopped' })).toBeVisible();
  await page.getByRole('button', { name: /Resume sending/ }).click();
  await expect(page.getByRole('alert').filter({ hasText: 'Sending is stopped' })).toHaveCount(0);
});

test('local search shows ranked results, a detail drawer with reasons, and saves to Clients', async ({ page }) => {
  await page.route('**/api/hunt/local', (route) => route.fulfill({ json: { provider: 'osm', count: 2, notes: [], results: [
    { provider: 'osm', place_id: 'osm_node_1', name: 'Smile Dental', website: null, domain: null, address: '1 High St', phone: '555-0100', rating: null, reviews: 0, maps_url: null,
      classification: 'no_website_in_osm', verified_absence: false, issues: [], reasons: ['No website in OpenStreetMap (weaker evidence: verify)', 'Phone number available'], score: 40,
      pitch_strategy: { angle: 'Build a website customers can find and book from', value_estimate: null, deliverables: [], cold_pitch_hook: 'Hi, I couldn\'t find a website listed for Smile Dental in Leeds. Do you have one I missed?', actionable_teardown: [] } },
    { provider: 'osm', place_id: 'osm_node_2', name: 'Fine Site Co', website: 'https://fine.example', domain: 'fine.example', address: '2 High St', phone: null, rating: null, reviews: 0, maps_url: null,
      classification: 'has_site', verified_absence: false, issues: [], reasons: ['Has a working site (lower urgency)'], score: 10, pitch_strategy: null }] } }));
  await signIn(page);
  await page.getByRole('navigation', { name: 'Main' }).getByRole('button', { name: /^Find/ }).click();
  await page.getByPlaceholder('dentist, restaurant, plumber').fill('dentist');
  await page.getByPlaceholder('Leeds, UK').fill('Leeds');
  await page.getByRole('button', { name: 'Search', exact: true }).click();
  const rows = page.locator('tbody tr');
  await expect(rows).toHaveCount(2);
  await expect(rows.first()).toContainText('Smile Dental');                      // best opportunity first
  await expect(rows.first()).toContainText('verify first');                       // OSM absence is not presented as proof
  await page.getByRole('button', { name: 'Smile Dental' }).click();
  const drawer = page.getByRole('dialog', { name: 'Smile Dental' });
  await expect(drawer).toContainText('weaker evidence');
  await expect(drawer).toContainText("couldn't find a website");
  await page.keyboard.press('Escape');
  await expect(drawer).toHaveCount(0);
  await rows.first().getByRole('button', { name: 'Save' }).click();
  // saving one result opens its client page, where the honest state is shown: no website to audit, no contacts
  const client = page.getByRole('dialog', { name: 'Smile Dental' });
  await expect(client).toContainText('No website');
  await expect(client).toContainText('No contacts yet');
});

test('a client page shows honest empty states and never invents a contact', async ({ page, request }) => {
  const lead = await (await request.post('/api/pipeline/deals/create', { headers: await sessionHeaders(request), data: { company_name: 'E2E Client Co', domain: 'e2e-client.example' } })).json();
  await signIn(page);
  await page.getByRole('navigation', { name: 'Main' }).getByRole('button', { name: /^Clients/ }).click();
  await page.getByRole('button', { name: /E2E Client Co/ }).click();
  const drawer = page.getByRole('dialog', { name: 'E2E Client Co' });
  await expect(drawer).toContainText('No contacts yet');
  await expect(drawer).toContainText('Not audited yet');
  await expect(drawer).toContainText('not a chance of winning');
  await expect(drawer.getByRole('button', { name: 'Prepare first email' })).toBeDisabled();   // needs a recipient country first
  expect(lead.id).toBeGreaterThan(0);
});

test('integrations: a key is saved masked, never shown again, and can be removed', async ({ page }) => {
  await signIn(page);
  await page.getByRole('navigation', { name: 'Main' }).getByRole('button', { name: /^Settings/ }).click();
  await page.getByRole('navigation', { name: 'Settings sections' }).getByRole('button', { name: 'Integrations and keys' }).click();
  const secret = 'sk-e2e-SECRETVALUE-9876';
  await page.getByLabel('Anthropic (Claude) value').fill(secret);
  await page.getByRole('button', { name: 'Save' }).first().click();
  await expect(page.getByText('Saved in Settings').first()).toBeVisible();
  await expect(page.getByText('••••9876')).toBeVisible();
  expect(await page.content()).not.toContain('SECRETVALUE');                       // the value never comes back to the page
  await page.getByRole('button', { name: 'Remove' }).click();
  await expect(page.getByText('••••9876')).toHaveCount(0);
});

test('find on their website lists what the site publishes with sources, and only offers Add when an email is published', async ({ page, request }) => {
  const lead = await (await request.post('/api/pipeline/deals/create', { headers: await sessionHeaders(request), data: { company_name: 'Finder Co', domain: 'finder.example' } })).json();
  await page.route(`**/api/clients/${lead.id}/find_contacts`, (route) => route.fulfill({ json: { pages_checked: ['https://finder.example/team'], company_linkedin: null,
    linkedin_search_url: 'https://www.linkedin.com/search/results/people/?keywords=finder', limitations: ['A published email is not a verified one.'],
    candidates: [{ kind: 'person', name: 'Jane Doe', title: 'Chief Executive Officer', email: 'jane@finder.example', linkedin_url: null, source_url: 'https://finder.example/team', evidence: 'name and title shown together on the team page; email published beside the person' },
                 { kind: 'person', name: 'Raj Patel', title: 'Head of Engineering', email: null, linkedin_url: null, source_url: 'https://finder.example/team', evidence: 'name and title shown together on the team page; no email published' }] } }));
  await signIn(page);
  await page.getByRole('navigation', { name: 'Main' }).getByRole('button', { name: /^Clients/ }).click();
  await page.getByRole('button', { name: /Finder Co/ }).click();
  const drawer = page.getByRole('dialog', { name: 'Finder Co' });
  await drawer.getByRole('button', { name: 'Find on their website' }).click();
  await expect(drawer).toContainText('nothing is guessed');
  await expect(drawer).toContainText('Chief Executive Officer');
  await expect(drawer).toContainText('add an email by hand');                           // Raj has no published email: no Add button
  await drawer.getByRole('button', { name: 'Add', exact: true }).click();
  await expect(drawer).toContainText('unverified');                                      // saved, but never as verified
});

test('map view pins only businesses with exact coordinates', async ({ page }) => {
  await page.route('**/api/hunt/local', (route) => route.fulfill({ json: { provider: 'osm', count: 2, notes: [], results: [
    { provider: 'osm', place_id: 'a', name: 'Pinned Cafe', website: null, domain: null, address: 'x', phone: null, rating: null, reviews: 0, maps_url: null, classification: 'no_website_in_osm', verified_absence: false, issues: [], reasons: ['r'], score: 40, pitch_strategy: null, lat: 53.8, lon: -1.55, coords_approx: false },
    { provider: 'osm', place_id: 'b', name: 'Approx Cafe', website: null, domain: null, address: 'y', phone: null, rating: null, reviews: 0, maps_url: null, classification: 'no_website_in_osm', verified_absence: false, issues: [], reasons: ['r'], score: 30, pitch_strategy: null, lat: 53.79, lon: -1.54, coords_approx: true }] } }));
  await signIn(page);
  await page.getByRole('navigation', { name: 'Main' }).getByRole('button', { name: /^Find/ }).click();
  await page.getByPlaceholder('dentist, restaurant, plumber').fill('cafe');
  await page.getByPlaceholder('Leeds, UK').fill('Leeds');
  await page.getByRole('button', { name: 'Search', exact: true }).click();
  await page.getByRole('button', { name: /^Map \(1\)/ }).click();                       // one exact pin; the city-centre fallback is not pinned
  await expect(page.getByRole('img', { name: 'Map of 1 businesses' })).toBeVisible();
  await expect(page.getByText('1 result(s) have no exact coordinates')).toBeVisible();
});


test('smart search corrects typos, explains what it understood, and runs the right search', async ({ page }) => {
  await page.route('**/api/hunt/local', (route) => route.fulfill({ json: { provider: 'osm', count: 1, notes: [], results: [
    { provider: 'osm', place_id: 'osm_node_9', name: 'Leeds Dental Care', website: null, domain: null, address: '9 High St', phone: null, rating: null, reviews: 0, maps_url: null, classification: 'no_website_in_osm',
      verified_absence: false, issues: [], reasons: ['No website in OpenStreetMap (weaker evidence: verify)'], score: 35, pitch_strategy: null }] } }));
  await signIn(page);
  await page.getByRole('navigation', { name: 'Main' }).getByRole('button', { name: /^Find/ }).click();
  const box = page.getByLabel('Search for clients, businesses, jobs or tenders');
  await box.fill('dent');
  await expect(page.getByRole('option', { name: /dentist/ })).toBeVisible();                       // suggestions while typing
  await box.fill('dentst in leeds without a website');
  await page.getByRole('button', { name: /^Go/ }).click();
  await expect(page.getByText('Did you mean dentist? (typed dentst)')).toBeVisible();
  await expect(page.getByText(/Searching local businesses: dentist, in Leeds, with no website/)).toBeVisible();
  await expect(page.locator('tbody tr')).toHaveCount(1);                                           // and it ran the local search by itself
  await expect(page.getByPlaceholder('dentist, restaurant, plumber')).toHaveValue('dentist');
});

test('smart search sends skill and budget requests to Jobs with the filters filled in', async ({ page }) => {
  await signIn(page);
  await page.getByRole('navigation', { name: 'Main' }).getByRole('button', { name: /^Find/ }).click();
  await page.getByLabel('Search for clients, businesses, jobs or tenders').fill('reakt developer remote over 5k');
  await page.getByRole('button', { name: /^Go/ }).click();
  await expect(page.getByText('Did you mean react? (typed reakt)')).toBeVisible();
  await expect(page.getByRole('tab', { name: /Jobs and projects/ })).toHaveAttribute('aria-selected', 'true');
  await expect(page.getByPlaceholder('react, tender, fintech…')).toHaveValue('react');
  await expect(page.getByLabel('Remote only')).toBeChecked();
  await expect(page.getByPlaceholder('any').first()).toHaveValue('5000');
});

test('nonsense is not guessed at, and an ambiguous request asks for what is missing', async ({ page }) => {
  await signIn(page);
  await page.getByRole('navigation', { name: 'Main' }).getByRole('button', { name: /^Find/ }).click();
  const box = page.getByLabel('Search for clients, businesses, jobs or tenders');
  await box.fill('zzzz qqqq');
  await page.getByRole('button', { name: /^Go/ }).click();
  await expect(page.getByText('I could not tell what to search for.')).toBeVisible();
  await box.fill('need a plumber');
  await page.getByRole('button', { name: /^Go/ }).click();
  await expect(page.getByText(/Add a city to search local businesses/)).toBeVisible();
});

test('tools page lists every utility and where the old pages went', async ({ page }) => {
  await signIn(page);
  await page.getByRole('navigation', { name: 'Main' }).getByRole('button', { name: /^Tools/ }).click();
  for (const t of ['Site Clinic', 'Compare two sites', 'Client report', 'Find an email address', 'Email draft checker', 'Email sequences', 'Call notes to scope of work', 'Video pitch script'])
    await expect(page.getByRole('button', { name: new RegExp(t) })).toBeVisible();
  await expect(page.getByText('Where did my old pages go?')).toBeVisible();
  await page.getByRole('button', { name: /Compare two sites/ }).click();
  await expect(page.getByLabel('Prospect website')).toBeVisible();
  await page.getByRole('button', { name: 'All tools' }).click();
  await expect(page.getByText('Mission Control')).toBeVisible();
});


test('sidebar: collapses to a rail with tooltips, remembers the choice, and keyboard shortcuts navigate', async ({ page }) => {
  await signIn(page);
  const side = page.getByRole('navigation', { name: 'Main' });
  await expect(side.getByText('Workspace')).toBeVisible();
  await page.getByRole('button', { name: 'Collapse sidebar' }).click();
  await expect(side.getByText('Workspace')).toHaveCount(0);                                  // rail: labels hidden
  await expect(side.getByRole('button', { name: 'Find' })).toBeVisible();                    // but still reachable by name
  await page.reload();
  await expect(page.getByRole('navigation', { name: 'Main' })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Expand sidebar' })).toBeVisible();          // remembered after a reload
  await page.getByRole('button', { name: 'Expand sidebar' }).click();
  await page.keyboard.press('g'); await page.keyboard.press('s');
  await expect(page.getByRole('heading', { level: 1, name: 'Settings' })).toBeVisible();
  await page.keyboard.press('g'); await page.keyboard.press('f');
  await expect(page.getByRole('heading', { level: 1, name: 'Find' })).toBeVisible();
  await page.keyboard.press('?');
  await expect(page.getByRole('dialog', { name: 'Keyboard shortcuts' })).toBeVisible();
  await page.keyboard.press('Escape');
  await page.getByLabel('Search for clients, businesses, jobs or tenders').focus();
  await page.keyboard.press('g'); await page.keyboard.press('s');                           // typing in a field never triggers shortcuts
  await expect(page.getByRole('heading', { level: 1, name: 'Find' })).toBeVisible();
});

test('account menu lives in the sidebar and signs out', async ({ page }) => {
  await signIn(page);
  await page.getByRole('button', { name: 'Account menu' }).click();
  await expect(page.getByRole('menuitem', { name: /Keyboard shortcuts/ })).toBeVisible();
  await page.getByRole('menuitem', { name: 'Sign out' }).click();
  await expect(page.getByLabel('Tier')).toBeVisible();
});

for (const [name, size] of [['phone', { width: 375, height: 812 }], ['tablet', { width: 820, height: 1180 }]] as const) {
  test(`responsive (${name}): drawer or tab bar, no horizontal scrolling on any screen`, async ({ page }) => {
    await page.setViewportSize(size);
    await signIn(page).catch(async () => undefined);
    const overflow = () => page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
    const bar = page.getByRole('navigation', { name: 'Mobile' });
    await expect(bar).toBeVisible();                                                           // bottom tab bar below 1024px
    for (const s of SURFACES) {
      await bar.getByRole('button', { name: s }).click();
      await page.waitForTimeout(500);
      expect(await overflow(), `${name}: ${s} scrolls sideways`).toBeLessThanOrEqual(0);
    }
    await page.getByRole('button', { name: 'Open menu' }).click();
    await expect(page.getByRole('dialog', { name: 'Menu' })).toBeVisible();                    // drawer with the full sidebar
    await page.getByRole('dialog', { name: 'Menu' }).getByRole('button', { name: /^Find/ }).click();
    await expect(page.getByRole('dialog', { name: 'Menu' })).toHaveCount(0);
    await expect(page.getByRole('heading', { level: 1, name: 'Find' })).toBeVisible();
  });
}

async function openChannel(page: Page, name: string) {
  await signIn(page);
  await page.getByRole('navigation', { name: 'Main' }).getByRole('button', { name: /^Channels/ }).click();
  await page.getByRole('tab', { name: new RegExp(`^${name}`) }).click();
}

test('channels: fiverr states plainly that nothing logs in, refreshes or fakes being online', async ({ page }) => {
  await openChannel(page, 'Fiverr');
  const box = page.locator('section', { hasText: 'How Fiverr works here' });
  await expect(box).toContainText(/never logs in/i);
  await expect(box).toContainText(/does not refresh pages or fake being online/i);
  await expect(page.getByLabel(/password/i)).toHaveCount(0);
  await expect(page.locator('iframe')).toHaveCount(0);
});

test('channels: routine tick, application log with follow-up, and reply-time log persist', async ({ page }) => {
  await openChannel(page, 'Upwork');
  const first = page.getByRole('checkbox', { name: /: (done|not done)$/ }).first();         // the routine items, not any other checkbox on the page
  await first.click();
  await expect(first).toHaveAttribute('aria-checked', 'true');

  await page.getByLabel('Title', { exact: true }).fill('E2E dashboard rebuild');
  await page.getByLabel('Client', { exact: true }).fill('Acme Ltd');
  await page.getByLabel('Value in dollars').fill('1200');
  await page.getByRole('button', { name: 'Log it' }).click();
  await expect(page.getByText('E2E dashboard rebuild')).toBeVisible();
  await page.getByLabel('Follow up date for E2E dashboard rebuild').fill('2020-01-01');
  await expect(page.getByText('Follow up', { exact: true }).first()).toBeVisible();

  await page.getByLabel('Message note').fill('E2E client');
  await page.getByRole('button', { name: 'Message received now' }).click();
  await page.getByRole('button', { name: 'I replied' }).first().click();
  await expect(page.locator('li').filter({ hasText: 'E2E client' }).getByText('Replied')).toBeVisible();

  await page.reload();
  await page.getByRole('navigation', { name: 'Main' }).getByRole('button', { name: /^Channels/ }).click();
  await page.getByRole('tab', { name: /^Upwork/ }).click();
  await expect(page.getByText('E2E dashboard rebuild').last()).toBeVisible();
  await expect(page.getByRole('checkbox', { name: /: (done|not done)$/ }).first()).toHaveAttribute('aria-checked', 'true');
});

test('channels: linkedin builds plain search links and a 300 character counter', async ({ page }) => {
  await openChannel(page, 'LinkedIn');
  await page.getByLabel('Company name').fill('Acme Robotics');
  await page.getByRole('button', { name: 'Build links' }).click();
  const link = page.getByRole('link', { name: /LinkedIn people at Acme Robotics/ });
  await expect(link).toHaveAttribute('href', /linkedin\.com\/search\/results\/people/);
  await expect(link).toHaveAttribute('rel', /noopener/);
  await expect(page.getByText(/\/300/).first()).toBeVisible();
});

test('today: the focus strip comes first, then the tier dashboard with real numbers and no invented health claim', async ({ page }) => {
  await signIn(page);
  await expect(page.getByRole('heading', { name: /Good (morning|afternoon|evening)/ })).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Workspace Operations & Governance' })).toBeVisible();
  await expect(page.getByText('Total Commercial Pipeline')).toBeVisible();
  await expect(page.getByText('Setup checks')).toBeVisible();                                             // read from the live system checks
  await expect(page.getByText('From the live system checks')).toBeVisible();
  await expect(page.getByText('100% OK')).toHaveCount(0);                                                  // the earlier hard-coded "API health" is gone
  await expect(page.getByText('174 endpoints')).toHaveCount(0);
});

test('browser dock lists every site and opens pages in one docked window', async ({ page }) => {
  await page.addInitScript(() => {
    (window as any).__opened = [];
    window.open = ((url: string, name: string, features: string) => { (window as any).__opened.push({ url: String(url), name, features }); return {} as Window; }) as typeof window.open;
  });
  await signIn(page);
  await page.getByRole('button', { name: 'Browser dock' }).click();
  const dock = page.getByRole('dialog', { name: 'Browser dock' });
  for (const site of ['LinkedIn', 'Fiverr', 'Upwork', 'Freelancer.com']) await expect(dock.getByText(site, { exact: true })).toBeVisible();
  await dock.getByRole('button', { name: 'Seller dashboard' }).click();
  await dock.getByRole('button', { name: 'Inbox' }).click();
  const opened = await page.evaluate(() => (window as any).__opened);
  expect(opened.map((o: any) => o.url)).toEqual(['https://www.fiverr.com/seller_dashboard', 'https://www.fiverr.com/inbox']);
  expect(new Set(opened.map((o: any) => o.name)).size).toBe(1);
  expect(opened[0].features).toContain('popup');
  await dock.getByLabel('Address to open').fill('javascript:alert(1)');
  await dock.getByRole('button', { name: 'Open', exact: true }).click();
  expect((await page.evaluate(() => (window as any).__opened)).length).toBe(2);
  await expect(dock.getByRole('alert')).toBeVisible();
});

test('channels: each site lists its features, pages and weekly ratios from logged numbers', async ({ page }) => {
  await openChannel(page, 'Fiverr');
  await expect(page.getByRole('heading', { name: 'What Fiverr offers' })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Seller dashboard' })).toBeVisible();
  await page.getByLabel('Activity', { exact: true }).selectOption('gig_impressions');
  await page.getByLabel('How many').fill('200');
  await page.getByRole('button', { name: 'Add for today' }).click();
  await page.getByLabel('Activity', { exact: true }).selectOption('gig_clicks');
  await page.getByLabel('How many').fill('10');
  await page.getByRole('button', { name: 'Add for today' }).click();
  await expect(page.getByText('5%', { exact: true })).toBeVisible();
});

test('channels: application list filters by status and searches', async ({ page }) => {
  await openChannel(page, 'Contra');
  for (const [t, st] of [['Alpha site', 'applied'], ['Beta app', 'won']]) {
    await page.getByLabel('Title', { exact: true }).fill(t);
    await page.getByLabel('Status', { exact: true }).selectOption(st);
    await page.getByRole('button', { name: 'Log it' }).click();
    await expect(page.getByText(t).first()).toBeVisible();
  }
  await page.getByRole('group', { name: 'Filter by status' }).getByRole('button', { name: /^Won/ }).click();
  await expect(page.getByText('Alpha site')).toHaveCount(0);
  await expect(page.getByText('Beta app')).toBeVisible();
});

test('clients: notes and a due follow-up task show on Today, can be ticked off; board searches and exports', async ({ page }) => {
  await signIn(page);
  const nav = page.getByRole('navigation', { name: 'Main' });
  await nav.getByRole('button', { name: /^Clients/ }).click();
  await page.getByRole('button', { name: 'Add client' }).click();
  await page.getByLabel('Company').fill('Notes Test Dental');
  await page.getByLabel('Website').fill('notes-test-dental.example');
  await page.getByRole('button', { name: 'Save', exact: true }).click();
  await page.getByRole('button', { name: /Notes Test Dental/ }).first().click();
  const drawer = page.getByRole('dialog');
  await drawer.getByRole('button', { name: 'Note', exact: true }).click();
  await drawer.getByLabel('Note', { exact: true }).fill('Owner wants a quote by Friday.');
  await drawer.getByRole('button', { name: 'Add note' }).click();
  await expect(drawer.getByText('Owner wants a quote by Friday.')).toBeVisible();
  await drawer.getByRole('button', { name: 'Follow-up task' }).click();
  await drawer.getByLabel('Task', { exact: true }).fill('Send the quote');
  await drawer.locator('input[type=date]').fill('2020-01-01');
  await drawer.getByRole('button', { name: 'Add task' }).click();
  await expect(drawer.getByText('Send the quote')).toBeVisible();
  await page.keyboard.press('Escape');


  await nav.getByRole('button', { name: /^Today/ }).click();
  await expect(page.getByRole('heading', { name: 'Client follow-ups' })).toBeVisible();
  await expect(page.getByText('Send the quote').first()).toBeVisible();
  await page.getByText('Send the quote').first().click();
  await page.getByRole('dialog').getByRole('checkbox', { name: /Send the quote/ }).click();
  await expect(page.getByRole('dialog').getByRole('checkbox', { name: /Send the quote: done/ })).toBeVisible();
});

test('find: recent searches are remembered and can be cleared', async ({ page }) => {
  await page.route('**/api/hunt/local', (r) => r.abort());          // no live map lookups in tests
  await signIn(page);
  await page.getByRole('navigation', { name: 'Main' }).getByRole('button', { name: /^Find/ }).click();
  await page.getByLabel('Search for clients, businesses, jobs or tenders').fill('plumbers in Manchester');
  await page.getByRole('button', { name: /^Go/ }).click();
  await expect(page.getByLabel('Recent searches').getByRole('button', { name: 'plumbers in Manchester' })).toBeVisible();
  await page.getByLabel('Recent searches').getByRole('button', { name: 'Clear' }).click();
  await expect(page.getByLabel('Recent searches')).toHaveCount(0);
});

test('channels: one sentence becomes a draft you confirm; a missing platform is asked for, not guessed', async ({ page }) => {
  await signIn(page);
  await page.getByRole('navigation', { name: 'Main' }).getByRole('button', { name: /^Channels/ }).click();
  const box = page.getByLabel('Log in plain words');
  await box.fill('applied to react dashboard rebuild on upwrok $1200 follow up friday');
  await page.getByRole('button', { name: 'Read it' }).click();
  const draft = page.getByRole('group', { name: 'Draft to confirm' });
  await expect(draft.getByText(/Read 'upwrok' as Upwork/)).toBeVisible();
  await expect(draft.getByLabel('Title')).toHaveValue('react dashboard rebuild');
  await expect(draft.getByLabel('Value $')).toHaveValue('1200');
  await draft.getByRole('button', { name: 'Save to pipeline' }).click();
  await expect(page.getByRole('tab', { name: /^Upwork/ })).toHaveAttribute('aria-selected', 'true');
  await expect(page.getByText('react dashboard rebuild').last()).toBeVisible();

  await box.fill('react developer job $500');
  await page.getByRole('button', { name: 'Read it' }).click();
  await expect(draft.getByText(/Still needed: the platform/)).toBeVisible();
  await expect(draft.getByRole('button', { name: 'Save to pipeline' })).toBeDisabled();
});

test('find: business type and city fields suggest, tolerate typos, and work from the keyboard', async ({ page }) => {
  await signIn(page);
  await page.getByRole('navigation', { name: 'Main' }).getByRole('button', { name: /^Find/ }).click();
  const type = page.getByPlaceholder('dentist, restaurant, plumber');
  await type.fill('dentst');
  await expect(page.getByRole('option', { name: 'dentist' })).toBeVisible();
  await type.press('ArrowDown');
  await type.press('Enter');
  await expect(type).toHaveValue('dentist');
  const city = page.getByPlaceholder('Leeds, UK');
  await city.fill('new y');
  await page.getByRole('option', { name: 'New York' }).click();
  await expect(city).toHaveValue('New York');
});

test('command palette understands a sentence: search it, or log it', async ({ page }) => {
  await page.route('**/api/hunt/local', (r) => r.abort());          // no live map lookups in tests
  await signIn(page);
  await page.keyboard.press('Control+k');
  await page.getByLabel('Go to').fill('dentists in leeds without a website');
  await page.keyboard.press('Enter');
  await expect(page.getByRole('heading', { level: 1, name: 'Find' })).toBeVisible();
  await expect(page.getByRole('status').filter({ hasText: /dentist/i }).first()).toBeVisible();

  await page.keyboard.press('Control+k');
  await page.getByLabel('Go to').fill('applied web design bid on guru $300');
  await page.keyboard.press('ArrowDown');
  await page.keyboard.press('Enter');
  await expect(page.getByRole('heading', { level: 1, name: 'Channels' })).toBeVisible();
  await expect(page.getByRole('group', { name: 'Draft to confirm' }).getByLabel('Title')).toHaveValue('web design');
});

test('linkedin: invite pacing counts a rolling week against your own limit and warns when over', async ({ page }) => {
  await signIn(page);
  await page.getByRole('navigation', { name: 'Main' }).getByRole('button', { name: /^Channels/ }).click();
  await page.getByRole('tab', { name: /^LinkedIn/ }).click();
  await page.getByLabel('Activity', { exact: true }).selectOption('invite_sent');
  await page.getByLabel('How many').fill('90');
  await page.getByRole('button', { name: 'Add for today' }).click();
  await expect(page.getByText('Over your limit: pause new invites')).toBeVisible();
  await expect(page.getByRole('progressbar', { name: 'Invites used' })).toBeVisible();
});

test('channels: funnel and cost per win come from logged applications; changes come due for review', async ({ page }) => {
  await signIn(page);
  await page.getByRole('navigation', { name: 'Main' }).getByRole('button', { name: /^Channels/ }).click();
  await page.getByRole('tab', { name: /^Guru/ }).click();
  for (const [t, st, cost] of [['Job A', 'applied', '3'], ['Job B', 'won', '3']]) {
    await page.getByLabel('Title', { exact: true }).fill(t);
    await page.getByLabel('Status', { exact: true }).selectOption(st);
    await page.getByLabel('Cost to apply in dollars').fill(cost);
    await page.getByRole('button', { name: 'Log it' }).click();
    await expect(page.getByText(t).first()).toBeVisible();
  }
  const funnel = page.locator('section', { hasText: 'Your funnel' });
  await expect(funnel.getByText('50%').first()).toBeVisible();
  await expect(funnel.getByText('$6', { exact: true }).first()).toBeVisible();
  await page.getByLabel('What did you change').fill('New headline');
  await page.getByLabel('Changed on').fill('2020-01-01');
  await page.getByRole('button', { name: 'Log change' }).click();
  await expect(page.getByText('Review now')).toBeVisible();
});

test('search boxes clear with a button and with Escape', async ({ page }) => {
  await signIn(page);
  await page.getByRole('navigation', { name: 'Main' }).getByRole('button', { name: /^Channels/ }).click();
  await page.getByRole('tab', { name: /^Contra/ }).click();
  await page.getByLabel('Title', { exact: true }).fill('Clear test');
  await page.getByRole('button', { name: 'Log it' }).click();
  const search = page.getByRole('searchbox', { name: 'Search applications' });
  await search.fill('zzz');
  await page.getByRole('button', { name: 'Clear search applications' }).click();
  await expect(search).toHaveValue('');
  await search.fill('abc');
  await search.press('Escape');
  await expect(search).toHaveValue('');
});

const json = (body: unknown, status = 200) => ({ status, contentType: 'application/json', body: JSON.stringify(body) });
const FINDINGS = [
  { category: 'security', check_id: 'missing_hsts', severity: 'high', finding: 'No HSTS header (Strict-Transport-Security).', fix: 'Send Strict-Transport-Security once HTTPS works everywhere.', estimated_impact: 'Browsers will not force HTTPS on return visits.', service_id: 'security_hardening', evidence_value: "Header 'Strict-Transport-Security' not present.", confidence: 1, evidence_id: 3 },
  { category: 'seo', check_id: 'no_sitemap', severity: 'medium', finding: 'No XML sitemap found.', fix: 'Generate sitemap.xml and list it in robots.txt.', estimated_impact: 'Search engines find pages more slowly.', service_id: 'seo_optimization', evidence_value: 'sitemap.xml missing.', confidence: 1, evidence_id: 9 },
  { category: 'a11y', check_id: 'img_alt', severity: 'low', finding: 'Images without alt text.', fix: 'Add alt text.', estimated_impact: 'Screen readers skip them.', service_id: 'accessibility', evidence_value: '3 of 8 images.', confidence: 1, evidence_id: 11 },
  { category: 'seo', check_id: 'no_og', severity: 'info', finding: 'No Open Graph tags.', fix: null, estimated_impact: null, service_id: null, evidence_value: null, confidence: 1, evidence_id: 12 },
];
async function mockClinic(page: Page, resolveReplies: unknown[]) {
  let n = 0;
  await page.route('**/api/companies/resolve', (r) => r.fulfill(json(resolveReplies[Math.min(n++, resolveReplies.length - 1)])));
  await page.route('**/api/audits/run', (r) => r.fulfill(json({ audit_id: 1, domain: 'acmeplumbing.com', overall_score: 42, status: 'completed', response_time_ms: 120, findings_count: 4, findings: FINDINGS })));
  await page.route('**/api/companies/1/brief', (r) => r.fulfill(json({ status: 'ok', unknown: ['Revenue'], pitch_kit: { angle: { text: 'Lead with security hardening.' }, price_band: null, price_band_note: 'No price band set for this service.', talking_points: [{ text: 'No HSTS header. (measured: not present)', evidence_ids: [3] }], objections_to_prepare_for: { items: ['No budget this quarter.'] } } })));
  await page.route('**/api/companies/1/advice', (r) => r.fulfill(json({ recommendations: [{ service_key: 'security_hardening', service: 'Security hardening', priority: 'high', price_band: null, summary: '1 finding(s)', findings: [{ finding: 'No HSTS', severity: 'high', fix: 'Send HSTS', evidence_id: 3 }] }] })));
  await page.route('**/api/companies/1/audit_history', (r) => r.fulfill(json({ audits: [], change: { latest_audit_id: 2, previous_audit_id: 1, score_before: 30, score_after: 42, score_delta: 12, previous_at: '2026-10-01 10:00:00', latest_at: '2026-10-25 10:00:00', still_open: 2, fixed: [{ check_id: 'x', severity: 'low', finding: 'Missing favicon' }], new: [] } })));
  await page.route('**/api/companies/1/teardown', (r) => r.fulfill(json({ markdown: '# Website teardown: Acme Plumbing\n\n## Findings (3)', filename: 'Teardown_Acme_Plumbing.md' })));
  await page.route('**/api/companies/1/offer', (r) => r.fulfill(json({ markdown: '# Fixed-price offer for Acme Plumbing\n\nPrice: [your fixed price]', filename: 'Offer_Acme_Plumbing.md', needs: ['Your price for Security hardening (Settings > Services and proof).', 'Your delivery time.'] })));
  await page.route('**/api/companies/presence', (r) => r.fulfill(json({ verified: false, confidence: 0.6, classification: 'has_website', checks_performed: [{ check: 'domain', outcome: 'resolves' }], limitations: ['Could not confirm the address.'] })));
}
async function openTools(page: Page) {
  await signIn(page);
  await page.getByRole('navigation', { name: 'Main' }).getByRole('button', { name: /^Tools/ }).click();
}

test('site clinic: paste a business and place, get a chart, a diagnosis, a surgery plan you tick off, and a teardown', async ({ page }) => {
  await mockClinic(page, [{ company_id: 1, name: 'Acme Plumbing', domain: 'acmeplumbing.com', status: 'resolved', confidence: 1, candidates: [] }]);
  await openTools(page);
  await page.getByLabel('Paste a website or a business and place').fill('Acme Plumbing, Austin');
  await page.getByRole('button', { name: 'Examine', exact: true }).click();
  await expect(page.getByRole('heading', { level: 1, name: 'Site Clinic' })).toBeVisible();
  await expect(page.getByText('+12 since last check')).toBeVisible();
  await expect(page.getByText('Fixed since 2026-10-01 (1)')).toBeVisible();
  await expect(page.getByText('Security: 1')).toBeVisible();

  await page.getByRole('button', { name: /No HSTS header \(Strict/ }).first().click();
  await expect(page.getByText("Header 'Strict-Transport-Security' not present.")).toBeVisible();      // the measurement behind the claim
  await page.getByRole('tab', { name: /^Medium/ }).click();
  await expect(page.getByText('No XML sitemap found.').first()).toBeVisible();

  const plan = page.locator('section', { hasText: 'Surgery plan' });
  await expect(plan.getByText('0/3 done')).toBeVisible();                                           // the info-level item is not an operation
  await plan.getByRole('checkbox', { name: /No HSTS header.*not done/ }).click();
  await expect(plan.getByText('1/3 done')).toBeVisible();
  await expect(plan.getByText('No price band set for this service.')).toBeVisible();                 // no invented price
  await expect(page.getByText('Web presence')).toBeVisible();

  await page.getByRole('button', { name: 'Teardown' }).click();
  await expect(page.getByRole('dialog', { name: 'Website teardown' })).toContainText('Website teardown: Acme Plumbing');
  await page.keyboard.press('Escape');

  await page.getByRole('button', { name: 'Offer', exact: true }).click();                                // the offer lists what only you can fill in
  const offer = page.getByRole('dialog', { name: 'Fixed-price offer' });
  await expect(offer).toContainText('Fixed-price offer for Acme Plumbing');
  await expect(offer).toContainText('never makes up a price or a date');
  await expect(offer).toContainText('Your price for Security hardening');
  await page.keyboard.press('Escape');
});

test('site clinic: a name that cannot be pinned down offers real candidates and guesses nothing', async ({ page }) => {
  await mockClinic(page, [
    { company_id: 1, name: 'Acme', domain: null, status: 'ambiguous', confidence: 0.4, note: 'Two sites could match.', candidates: [{ domain: 'acmeplumbing.com', score: 0.7 }] },
    { company_id: 1, name: 'Acme Plumbing', domain: 'acmeplumbing.com', status: 'resolved', confidence: 1, candidates: [] },
  ]);
  await openTools(page);
  await page.getByLabel('Paste a website or a business and place').fill('Acme in Austin');
  await page.getByRole('button', { name: 'Examine', exact: true }).click();
  await expect(page.getByText('Could not pin down the site')).toBeVisible();
  await expect(page.getByText('Nothing was guessed.')).toBeVisible();
  await page.getByRole('button', { name: /acmeplumbing\.com 70%/ }).click();
  await expect(page.getByText('Health score')).toBeVisible();
});

test('site clinic: bad input is explained, and the result carries over to Compare', async ({ page }) => {
  await mockClinic(page, [{ company_id: 1, name: 'Acme Plumbing', domain: 'acmeplumbing.com', status: 'resolved', confidence: 1, candidates: [] }]);
  await openTools(page);
  await page.getByLabel('Paste a website or a business and place').fill('x');
  await page.getByLabel('Paste a website or a business and place').press('Enter');
  await expect(page.getByRole('alert').filter({ hasText: 'Paste a website' })).toBeVisible();
  await page.getByLabel('Paste a website or a business and place').fill('https://www.acmeplumbing.com/contact');
  await page.getByRole('button', { name: 'Examine', exact: true }).click();
  await expect(page.getByText('Health score')).toBeVisible();
  await page.getByRole('button', { name: 'Compare', exact: true }).click();
  await expect(page.getByLabel('Prospect website')).toHaveValue('acmeplumbing.com');
});

test('tools: search narrows the cards by what they do, and recent tools are remembered', async ({ page }) => {
  await openTools(page);
  await page.getByRole('searchbox', { name: 'Search tools' }).fill('competitor');
  await expect(page.getByRole('button', { name: /Compare two sites/ })).toBeVisible();
  await expect(page.getByRole('button', { name: /Video pitch script/ })).toHaveCount(0);
  await page.getByRole('searchbox', { name: 'Search tools' }).fill('zzzz');
  await expect(page.getByText(/No tool matches/)).toBeVisible();
  await page.getByRole('button', { name: 'Clear search tools' }).click();
  await page.getByRole('button', { name: /Video pitch script/ }).click();
  await page.getByRole('button', { name: 'All tools' }).click();
  await expect(page.getByLabel('Recent tools').getByRole('button', { name: 'Video pitch script' })).toBeVisible();
});

test('site clinic: a site that refuses robots is explained, not graded, and nothing is invented about it', async ({ page }) => {
  await mockClinic(page, [{ company_id: 1, name: 'cricinfo.com', domain: 'cricinfo.com', status: 'resolved', confidence: 0.5, access: 'blocked', note: 'The site answered (HTTP 403, AkamaiGHost) but refuses automated access.', candidates: [] }]);
  await page.route('**/api/audits/run', (r) => r.fulfill(json({
    audit_id: 5, domain: 'cricinfo.com', overall_score: null, status: 'blocked', response_time_ms: 0, findings_count: 1, checks_run: ['tls', 'email_dns'], checks_skipped: ['page checks'],
    blocked: { reason: 'HTTP 403', server: 'AkamaiGHost', status_code: 403 },
    findings: [{ category: 'performance', check_id: 'access_blocked', severity: 'info', finding: 'cricinfo.com answered with HTTP 403 (AkamaiGHost) and refused our automated request, so its pages were not checked.', fix: null, estimated_impact: null, service_id: null, evidence_value: 'Response: HTTP 403', confidence: 1, evidence_id: 7 }],
  })));
  await openTools(page);
  await page.getByLabel('Paste a website or a business and place').fill('https://www.cricinfo.com');
  await page.getByRole('button', { name: 'Examine', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'cricinfo.com refuses automated access' })).toBeVisible();
  await expect(page.getByText('Not graded', { exact: true }).first()).toBeVisible();
  await expect(page.getByText(/do not try to get around the protection/)).toBeVisible();
  await expect(page.getByRole('link', { name: 'Open it in your own browser' })).toHaveAttribute('href', 'https://cricinfo.com');
  await expect(page.getByText('Could not pin down the site')).toHaveCount(0);
  await expect(page.getByRole('button', { name: 'Teardown' })).toBeDisabled();                  // no teardown of a page we never read
  await expect(page.getByText(/\/100/)).toHaveCount(0);                                         // no score of any kind
});

test('ink and teal: light is the default, primary buttons are teal pills with white ink, cards are soft and frosted', async ({ page }) => {
  await signIn(page);
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'light');
  await page.getByRole('navigation', { name: 'Main' }).getByRole('button', { name: /^Clients/ }).click();
  const add = page.getByRole('button', { name: 'Add client' });
  const style = await add.evaluate((el) => { const s = getComputedStyle(el); return { bg: s.backgroundImage, color: s.color, radius: s.borderRadius }; });
  expect(style.bg).toContain('linear-gradient');                                  // a lit teal, not flat
  expect(style.color).toBe('rgb(255, 255, 255)');                                  // white ink on deep teal (5.5:1)
  expect(parseFloat(style.radius)).toBeGreaterThan(100);                           // a pill
  const tile = await page.locator('.bento-tile').first().evaluate((el) => { const s = getComputedStyle(el); return { blur: s.backdropFilter || (s as any).webkitBackdropFilter, bg: s.backgroundColor }; });
  expect(tile.blur).toContain('blur');
  expect(tile.bg).toMatch(/rgba\(.*0\.\d+\)/);                                    // a translucent fill
  const bodyBg = await page.evaluate(() => getComputedStyle(document.body).backgroundImage);
  expect(bodyBg).toContain('radial-gradient');                                    // the teal light the cards sit on
});

test('ink and teal: the theme toggle switches to zinc ink and keeps the teal accent', async ({ page }) => {
  await signIn(page);
  await page.getByRole('button', { name: /dark|light/i }).first().click();
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'dark');
  const accent = await page.evaluate(() => getComputedStyle(document.documentElement).getPropertyValue('--color-indigo-500').trim());
  expect(accent.toLowerCase()).toBe('#2dd4bf');
  await page.reload();                                                             // the choice is remembered
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'dark');
});

for (const theme of ['light', 'dark'] as const) {
  test(`accessibility (${theme} theme): no serious contrast or other violations on every surface, the drawer and the palette`, async ({ page }) => {
    await page.addInitScript((t) => localStorage.setItem('agencybd_theme', t), theme);
    await signIn(page);
    const nav = page.getByRole('navigation', { name: 'Main' });
    const check = async (label: string) => {
      await page.waitForTimeout(600);
      const results = await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa']).analyze();
      const bad = results.violations.filter((v) => v.impact === 'serious' || v.impact === 'critical');
      expect(bad.map((v) => `${theme} ${label}: ${v.id} (${v.nodes.length}) ${v.nodes[0]?.html.slice(0, 90)}`), `axe on ${label}`).toEqual([]);
    };
    for (const s of SURFACES) { await nav.getByRole('button', { name: new RegExp(`^${s}`) }).click(); await check(s); }
    await page.getByRole('button', { name: 'Browser dock' }).click();
    await check('browser dock');
    await page.keyboard.press('Escape');
    await page.keyboard.press('Control+k');
    await page.getByLabel('Go to').fill('dentists in leeds');
    await check('command palette');
  });
}

async function openSettings(page: Page, section?: string) {
  await signIn(page);
  await page.getByRole('navigation', { name: 'Main' }).getByRole('button', { name: /^Settings/ }).click();
  if (section) await page.getByRole('navigation', { name: 'Settings sections' }).getByRole('button', { name: section }).click();
}

test('settings: sections are grouped, searchable, and Enter opens the best match', async ({ page }) => {
  await openSettings(page);
  const nav = page.getByRole('navigation', { name: 'Settings sections' });
  for (const s of ['Setup', 'Agency profile', 'Services and proof', 'Integrations and keys', 'Sending and policy', 'Domain DNS', 'Unsubscribe list', 'Access and passwords', 'Security and session', 'Data and export', 'Appearance and shortcuts', 'Developer', 'How it works'])
    await expect(nav.getByRole('button', { name: s })).toBeVisible();
  await expect(nav.getByText('Connections')).toBeVisible();
  const search = page.getByRole('searchbox', { name: 'Find a setting' });
  await search.fill('spf');
  await expect(nav.getByRole('button')).toHaveCount(1);                           // matched on what the section contains, not just its title
  await search.press('Enter');
  await expect(page.getByRole('heading', { level: 2, name: 'Domain DNS' })).toBeVisible();
  await search.fill('zzzz');
  await expect(page.getByText(/No setting matches/)).toBeVisible();
});

test('settings: every unfinished setup item has a button that goes to where it is fixed', async ({ page }) => {
  await openSettings(page);
  await expect(page.getByRole('img', { name: /percent of setup done/ })).toBeVisible();
  await page.getByRole('button', { name: /Fill the footer/ }).click();
  await expect(page.getByRole('heading', { level: 2, name: 'Agency profile' })).toBeVisible();
  await page.getByRole('navigation', { name: 'Settings sections' }).getByRole('button', { name: 'Setup' }).click();
  await page.getByRole('button', { name: /Add a case study/ }).click();
  await expect(page.getByRole('heading', { level: 2, name: 'Services and proof' })).toBeVisible();
});

test('settings: the agency profile validates, applies at once, gates the quoted result on proof, and resets', async ({ page }) => {
  await openSettings(page, 'Agency profile');
  await page.getByLabel('Postal address').fill('Main Street');
  await page.getByRole('button', { name: 'Save' }).nth(0).waitFor();
  const row = (label: string) => page.locator('li', { has: page.getByLabel(label, { exact: true }) });
  await row('Postal address').getByRole('button', { name: 'Save' }).click();
  await expect(row('Postal address').getByRole('alert')).toContainText(/street number|short|required/i);          // not saved: a real address is required

  await row('Postal address').getByLabel('Postal address').fill('12 High Street, Leeds LS1 4AB, UK');
  await row('Postal address').getByRole('button', { name: 'Save' }).click();
  await expect(row('Postal address').getByText('Saved and active now.')).toBeVisible();
  await row('Public address of this app').getByLabel('Public address of this app').fill('http://bd.example.com');
  await row('Public address of this app').getByRole('button', { name: 'Save' }).click();
  await expect(row('Public address of this app').getByRole('alert')).toContainText('https://');
  await row('Public address of this app').getByLabel('Public address of this app').fill('https://bd.example.com');
  await row('Public address of this app').getByRole('button', { name: 'Save' }).click();
  await expect(page.getByText('Legal footer complete')).toBeVisible();
  await expect(page.getByLabel('Email preview')).toContainText('12 High Street, Leeds LS1 4AB, UK');             // the preview is the real saved value

  await row('Result you quote').getByLabel('Result you quote').fill('Cut load time from 4s to 1s');
  await row('Result you quote').getByRole('button', { name: 'Save' }).click();
  await expect(row('Result you quote').getByRole('alert')).toContainText(/proven/i);                              // no quoted result without proof

  await row('Postal address').getByRole('button', { name: 'Reset to .env' }).click();
  await expect(page.getByText('Footer incomplete')).toBeVisible();
});

test('settings: data can be exported as CSV and shows what is stored', async ({ page }) => {
  await openSettings(page, 'Data and export');
  await expect(page.getByText('Clients', { exact: true }).first()).toBeVisible();
  const download = page.waitForEvent('download');
  await page.getByRole('button', { name: 'Download Clients as CSV' }).click();
  expect((await download).suggestedFilename()).toMatch(/^agencybd-clients-\d{8}\.csv$/);
  await expect(page.getByText('python3 scripts/backup_db.py')).toBeVisible();
});

test('settings: the theme can be chosen here, and security shows who you are and signs you out', async ({ page }) => {
  await openSettings(page, 'Appearance and shortcuts');
  await page.getByRole('radio', { name: /Dark/ }).click();
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'dark');
  await expect(page.getByText('Open the command palette')).toBeVisible();
  await page.getByRole('navigation', { name: 'Settings sections' }).getByRole('button', { name: 'Security and session' }).click();
  await expect(page.getByText(/super admin · workspace/)).toBeVisible();
  await expect(page.getByText('Everything.', { exact: false })).toBeVisible();
  await page.getByRole('button', { name: 'Sign out' }).click();
  await expect(page.getByRole('button', { name: 'Sign in' })).toBeVisible();
});

for (const theme of ['light', 'dark'] as const) {
  test(`accessibility (${theme}): the new settings sections have no serious violations`, async ({ page }) => {
    await page.addInitScript((t) => localStorage.setItem('agencybd_theme', t), theme);
    await openSettings(page);
    for (const s of ['Setup', 'Agency profile', 'Integrations and keys', 'Security and session', 'Data and export', 'Appearance and shortcuts']) {
      await page.getByRole('navigation', { name: 'Settings sections' }).getByRole('button', { name: s }).click();
      await page.waitForTimeout(700);
      const results = await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa']).analyze();
      const bad = results.violations.filter((v) => v.impact === 'serious' || v.impact === 'critical');
      expect(bad.map((v) => `${theme} ${s}: ${v.id} (${v.nodes.length}) ${v.nodes[0]?.html.slice(0, 100)}`)).toEqual([]);
    }
  });
}

test('find jobs: a short skill matches whole words only, so "ai" is not "email" and "seo" is not "Seoul"', async ({ page }) => {
  const opp = (id: number, title: string, description: string) => ({ id, type: 'hiring_signal', source: 'hn', external_id: `x${id}`, title, description, company_name: 'Acme', url: `https://example.com/${id}`, fit_score: 0.5, fit_reasons: [], budget_min: null, budget_max: null, currency: 'USD', created_at: '2026-10-20' });
  await page.route('**/api/opportunities*', (r) => r.fulfill(json([
    opp(1, 'AI engineer', 'Build LLM features'), opp(2, 'Office admin', 'Maintain email systems and said so'), opp(3, 'SEO specialist', 'Grow organic traffic'),
    opp(4, 'Seoul office manager', 'Based in Seoul'), opp(5, 'React developer', 'Frontend with reactjs'), opp(6, 'Proactive support agent', 'Customer care'),
  ])));
  await signIn(page);
  await page.getByRole('navigation', { name: 'Main' }).getByRole('button', { name: /^Find/ }).click();
  await page.getByRole('tab', { name: 'Jobs and projects' }).click();
  const search = page.getByPlaceholder('react, tender, fintech…');
  await search.fill('ai');
  await expect(page.getByText('AI engineer')).toBeVisible();
  await expect(page.getByText('Office admin')).toHaveCount(0);
  await search.fill('seo');
  await expect(page.getByText('SEO specialist')).toBeVisible();
  await expect(page.getByText('Seoul office manager')).toHaveCount(0);
  await search.fill('react');
  await expect(page.getByText('React developer').first()).toBeVisible();               // a longer term still finds "reactjs"
  await expect(page.getByText('Proactive support agent')).toHaveCount(0);
});

test('alert desk: settings explain the safe way it works, validate, and save a ladder you can edit', async ({ page }) => {
  await openSettings(page, 'Message alerts');
  await expect(page.getByText(/never logs in to Fiverr, Upwork or LinkedIn/)).toBeVisible();
  await expect(page.getByText('Mailbox not set up')).toBeVisible();
  await expect(page.getByRole('switch', { name: 'Alert Desk on or off' })).toHaveAttribute('aria-checked', 'false');

  await page.getByRole('group', { name: 'Presets' }).getByRole('button', { name: 'Persistent' }).click();
  await expect(page.getByLabel('Plan summary')).toContainText('WhatsApp right away → Phone call after 15 min → Phone call after 30 min → Phone call after 1 h');
  await page.getByRole('button', { name: 'Remove step 4' }).click();
  await page.getByRole('button', { name: 'Add a step' }).click();
  await page.getByLabel('Minutes for step 4').fill('45');
  await expect(page.getByLabel('Plan summary')).toContainText('Phone call after 45 min');

  await page.getByRole('textbox', { name: /Your phone number/ }).fill('03001234567');                      // not international: the server says so
  await page.getByRole('switch', { name: 'Alert Desk on or off' }).click();
  await page.getByRole('button', { name: 'Save alert settings' }).click();
  await expect(page.getByRole('alert').filter({ hasText: 'international form' })).toBeVisible();

  await page.getByRole('textbox', { name: /Your phone number/ }).fill('+92 340 4095953');
  await page.getByRole('button', { name: 'Save alert settings' }).click();
  await expect(page.getByText('Saved. The desk uses these settings from now on.')).toBeVisible();
  await page.reload();
  await page.getByRole('navigation', { name: 'Main' }).getByRole('button', { name: /^Settings/ }).click();
  await page.getByRole('navigation', { name: 'Settings sections' }).getByRole('button', { name: 'Message alerts' }).click();
  await expect(page.getByRole('switch', { name: 'Alert Desk on or off' })).toHaveAttribute('aria-checked', 'true');
  await expect(page.getByRole('textbox', { name: /Your phone number/ })).toHaveValue('+923404095953');       // normalised and remembered
  await expect(page.getByLabel('Plan summary')).toContainText('Phone call after 45 min');
});

test('alert desk: channels that are not set up say so, and tests are held back until they are', async ({ page }) => {
  await openSettings(page, 'Message alerts');
  for (const name of ['Telegram', 'ntfy push', 'WhatsApp', 'Phone call']) await expect(page.getByRole('heading', { name })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Test Telegram' })).toBeDisabled();
  await expect(page.getByRole('button', { name: 'Test Phone call' })).toBeDisabled();
  await expect(page.getByText(/Meta changed its pricing in October 2026/)).toBeVisible();                    // honest about WhatsApp cost
  await page.getByRole('button', { name: 'Make one' }).click();
  await expect(page.getByPlaceholder('agencybd-x7k2m9q4')).toHaveValue(/^agencybd-[a-z0-9]{14}$/);          // a hard-to-guess ntfy topic
});

test('alert desk: a client message shows on Channels and Today until you say you are on it', async ({ page }) => {
  await signIn(page);
  await page.getByRole('navigation', { name: 'Main' }).getByRole('button', { name: /^Channels/ }).click();
  await expect(page.getByText('Nothing waiting for a reply')).toBeVisible();
  await page.getByRole('button', { name: 'Add by hand' }).click();
  await page.getByLabel('Platform', { exact: true }).selectOption('fiverr');
  await page.getByLabel('Who wrote').fill('Amina K.');
  await page.getByLabel('What they wrote').fill('I need a website for my clinic. Can you start this week?');
  await page.locator('section').filter({ has: page.getByRole('heading', { name: 'Client messages' }) }).getByRole('button', { name: 'Add', exact: true }).click();
  await expect(page.getByText('I need a website for my clinic.')).toBeVisible();

  await page.getByRole('navigation', { name: 'Main' }).getByRole('button', { name: /^Today/ }).click();
  await expect(page.getByText('1 client message waiting for a reply: Amina K. on fiverr')).toBeVisible();

  await page.getByRole('navigation', { name: 'Main' }).getByRole('button', { name: /^Channels/ }).click();
  await page.getByRole('button', { name: "I'm on it: Amina K." }).click();
  await expect(page.getByText('Nothing waiting for a reply')).toBeVisible();
  await page.getByText(/Recently handled/).click();
  await expect(page.getByText(/Amina K. on fiverr.*acknowledged via app/)).toBeVisible();
});

test('alert desk: the new secrets are grouped, validated and never shown again', async ({ page }) => {
  await openSettings(page, 'Integrations and keys');
  await expect(page.getByRole('heading', { name: 'Message alerts' })).toBeVisible();
  const field = page.getByLabel('Telegram bot token value');
  await field.fill('not-a-token');
  await field.press('Enter');
  await expect(page.getByRole('alert').filter({ hasText: /Telegram token looks like/ })).toBeVisible();
  await field.fill('123456789:AAH-e2e-fake-token-for-validation-only-000');
  await field.press('Enter');
  await expect(page.getByText('Saved and active now.').first()).toBeVisible();
  await expect(page.getByText('••••-000')).toBeVisible();                                                   // only the last four characters, ever
  await expect(page.getByText('AAH-e2e-fake')).toHaveCount(0);
  await page.getByRole('button', { name: 'Remove' }).first().click();                                      // leave the test installation as it was
});

for (const theme of ['light', 'dark'] as const) {
  test(`accessibility (${theme}): the alert settings and the client messages panel`, async ({ page }) => {
    await page.addInitScript((t) => localStorage.setItem('agencybd_theme', t), theme);
    await openSettings(page, 'Message alerts');
    await page.waitForTimeout(700);
    const run = async (label: string) => {
      const results = await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa']).analyze();
      const bad = results.violations.filter((v) => v.impact === 'serious' || v.impact === 'critical');
      expect(bad.map((v) => `${theme} ${label}: ${v.id} (${v.nodes.length}) ${v.nodes[0]?.html.slice(0, 100)}`)).toEqual([]);
    };
    await run('message alerts');
    await page.getByRole('navigation', { name: 'Main' }).getByRole('button', { name: /^Channels/ }).click();
    await page.waitForTimeout(700);
    await run('client messages');
  });
}

async function openWatching(page: Page) {
  await signIn(page);
  await page.getByRole('navigation', { name: 'Main' }).getByRole('button', { name: /^Find/ }).click();
  await page.getByRole('tab', { name: 'Watching' }).click();
  await expect(page.getByRole('heading', { name: 'Watching for you' })).toBeVisible();
}

test('lead finder: a watch is saved, looks at once, can be paused and deleted, and mistakes are explained', async ({ page }) => {
  await openWatching(page);
  await expect(page.getByText('Nothing is being watched yet')).toBeVisible();
  await page.getByRole('button', { name: 'New watch' }).click();
  await page.getByLabel('Name', { exact: true }).fill('Shopify jobs');
  await page.getByLabel(/Words to look for/).fill('shopify, wordpress');
  await page.getByRole('button', { name: 'Save and look now' }).click();
  await expect(page.getByRole('status').filter({ hasText: /Saved\. First look found 0 matches/ })).toBeVisible();
  await expect(page.getByText('Shopify jobs')).toBeVisible();
  await expect(page.getByRole('listitem').getByText('Watching', { exact: true })).toBeVisible();
  await page.getByRole('button', { name: 'Pause Shopify jobs' }).click();
  await expect(page.getByRole('listitem').getByText('Paused', { exact: true })).toBeVisible();
  await page.getByRole('button', { name: 'Resume Shopify jobs' }).click();

  await page.getByRole('button', { name: 'New watch' }).click();                                              // a watch that needs a key says so, in plain words
  await page.getByLabel('What to watch').selectOption('new_companies');
  await page.getByLabel('Name', { exact: true }).fill('New UK firms');
  await expect(page.getByRole('button', { name: 'Add it in Settings' })).toBeVisible();
  await page.getByRole('button', { name: 'Save and look now' }).click();
  await expect(page.getByRole('status').filter({ hasText: /free Companies House key/ })).toBeVisible();

  await page.getByRole('button', { name: 'New watch' }).click();                                              // nothing chosen: a clear sentence, not a crash
  await page.getByLabel('What to watch').selectOption('site_signals');
  await page.getByLabel('Name', { exact: true }).fill('Fixable sites');
  await page.getByRole('button', { name: 'Save and look now' }).click();
  await expect(page.getByRole('alert').filter({ hasText: /at least one thing/ })).toBeVisible();

  for (const name of ['Shopify jobs', 'New UK firms']) await page.getByRole('button', { name: `Delete ${name}` }).click();
  await expect(page.getByText('Nothing is being watched yet')).toBeVisible();
});

test('lead finder: LinkedIn search links open in your own browser and nothing is fetched for you', async ({ page }) => {
  await openWatching(page);
  await page.getByRole('button', { name: 'Make links' }).click();                                            // the title is required
  await expect(page.locator('li a[href^="https://www.google.com/search"]')).toHaveCount(0);
  await page.getByLabel('Who (job title)').fill('practice manager');
  await page.getByLabel('Industry').fill('dental');
  await page.getByLabel('Place').fill('Dublin');
  await page.getByRole('button', { name: 'Make links' }).click();
  const first = page.getByRole('link', { name: /People on LinkedIn \(Google\)/ });
  await expect(first).toBeVisible();
  expect(await first.getAttribute('href')).toContain('site%3Alinkedin.com/in');
  expect(await first.getAttribute('rel')).toContain('noopener');
  await expect(page.getByRole('link', { name: /Who is hiring for it/ })).toBeVisible();
});

for (const theme of ['light', 'dark'] as const) {
  test(`accessibility (${theme}): the watching tab with the form open and links shown`, async ({ page }) => {
    await page.addInitScript((t) => localStorage.setItem('agencybd_theme', t), theme);
    await openWatching(page);
    await page.getByRole('button', { name: 'New watch' }).click();
    await page.getByLabel('Who (job title)').fill('owner');
    await page.getByRole('button', { name: 'Make links' }).click();
    await page.waitForTimeout(700);
    const results = await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa']).analyze();
    const bad = results.violations.filter((v) => v.impact === 'serious' || v.impact === 'critical');
    expect(bad.map((v) => `${theme}: ${v.id} (${v.nodes.length}) ${v.nodes[0]?.html.slice(0, 100)}`)).toEqual([]);
  });
}

test('chase today: a quiet client is listed with the reason, and picking a day sets a real follow-up task', async ({ page }) => {
  let list = [{ lead_id: 4242, company: 'Quiet Dental', stage: 'proposal_sent', stage_label: 'Proposal sent', days_quiet: 5, reason: 'x' }];
  await page.route('**/api/chase', (r) => r.fulfill({ json: { items: list, quiet_after_days: {} } }));
  let posted: { url: string; body: any } | null = null;
  await page.route('**/api/clients/4242/notes', (r) => { posted = { url: r.request().url(), body: r.request().postDataJSON() }; list = []; return r.fulfill({ json: { id: 1 } }); });
  await signIn(page);
  await page.getByRole('navigation', { name: 'Main' }).getByRole('button', { name: /^Clients/ }).click();
  await page.getByRole('tab', { name: /Pipeline/ }).click();
  await expect(page.getByRole('heading', { name: 'Chase today' })).toBeVisible();
  await expect(page.getByText('5 days quiet')).toBeVisible();
  await page.getByRole('button', { name: 'Tomorrow: follow up with Quiet Dental' }).click();
  await expect(page.getByRole('heading', { name: 'Chase today' })).toHaveCount(0);                              // planned, so it leaves the list
  expect(posted!.body.kind).toBe('task');
  expect(posted!.body.body).toBe('Follow up with Quiet Dental');
  expect(posted!.body.due_date).toMatch(/^\d{4}-\d{2}-\d{2}$/);
});

test('alert desk: a reply can be drafted from a client message, and the drafts ask rather than invent', async ({ page }) => {
  await signIn(page);
  await page.getByRole('navigation', { name: 'Main' }).getByRole('button', { name: /^Channels/ }).click();
  await page.getByRole('button', { name: 'Add by hand' }).click();
  await page.getByLabel('Platform', { exact: true }).selectOption('fiverr');
  await page.getByLabel('Who wrote').fill('Sara M.');
  await page.getByLabel('What they wrote').fill('How much for a new website for my bakery? When can you start?');
  await page.locator('section').filter({ has: page.getByRole('heading', { name: 'Client messages' }) }).getByRole('button', { name: 'Add', exact: true }).click();
  await page.getByRole('button', { name: 'Draft a reply to Sara M.' }).click();
  const ask = page.getByLabel('Draft reply: Ask first');
  await expect(ask).toHaveValue(/Hi Sara,/);
  await expect(ask).toHaveValue(/what budget you have in mind|budget do you have in mind/i);
  await expect(page.getByLabel('Draft reply: Give the price')).toHaveCount(0);                                 // no price was set, so none is stated
  await expect(page.getByText(/To improve these drafts:.*Your price/)).toBeVisible();
  await page.getByRole('button', { name: "I'm on it: Sara M." }).click();                                      // leave the test installation as it was
});

test('partners: add one, log contact and referrals, change the stage, and delete it', async ({ page }) => {
  await signIn(page);
  await page.getByRole('navigation', { name: 'Main' }).getByRole('button', { name: /^Clients/ }).click();
  await page.getByRole('tab', { name: 'Partners' }).click();
  await expect(page.getByText('No partners yet')).toBeVisible();
  await page.getByRole('button', { name: 'Add partner' }).click();
  await page.getByLabel('Name', { exact: true }).fill('Brightside Marketing');
  await page.getByLabel('Website').fill('not a site');
  await page.getByRole('button', { name: 'Save partner' }).click();
  await expect(page.getByRole('alert').filter({ hasText: /example\.com/ })).toBeVisible();                       // mistakes are explained
  await page.getByLabel('Website').fill('brightside.example');
  await page.getByLabel('What you will offer them').fill('10% on the first project');
  await page.getByRole('button', { name: 'Save partner' }).click();
  await expect(page.getByText('Brightside Marketing')).toBeVisible();
  await expect(page.getByLabel('Stage of Brightside Marketing')).toHaveValue('to_contact');
  await page.getByRole('button', { name: 'I contacted Brightside Marketing' }).click();
  await expect(page.getByLabel('Stage of Brightside Marketing')).toHaveValue('contacted');
  await page.getByRole('button', { name: 'Brightside Marketing sent me a client' }).click();
  await expect(page.getByLabel('Stage of Brightside Marketing')).toHaveValue('active_partner');
  await expect(page.getByText(/Sent to you: 1 · You sent: 0/)).toBeVisible();
  await expect(page.getByText('Clients they sent')).toBeVisible();
  await page.getByRole('button', { name: 'Delete Brightside Marketing' }).click();
  await expect(page.getByText('No partners yet')).toBeVisible();
});

test('today: the weekly scorecard compares with last week and shows a rate only when there is something to divide by', async ({ page }) => {
  const rows = (sent: number, replies: number) => [
    { key: 'sent', label: 'Emails sent', hint: '', this_week: sent, last_week: 4 }, { key: 'replies', label: 'Replies', hint: '', this_week: replies, last_week: 0 },
    { key: 'wins', label: 'Clients won', hint: '', this_week: 0, last_week: 0 }];
  await page.route('**/api/today/scorecard', (r) => r.fulfill({ json: { rows: rows(10, 2), reply_rate_percent: 20, last_reply_rate_percent: 0, winners_by_source: [{ source: 'local', n: 2 }], note: 'Counted from your own records.' } }));
  await signIn(page);
  const card = page.locator('section').filter({ has: page.getByRole('heading', { name: 'Your week' }) });
  await expect(card.getByText('up from 4')).toBeVisible();
  await expect(card.getByText('Reply rate')).toBeVisible();
  await expect(card.getByText('20%')).toBeVisible();
  await expect(card.getByText('Clients won')).toHaveCount(0);                                         // a metric that is zero in both weeks stays out of the way
  await expect(card.getByText('Where your won clients came from: local (2)')).toBeVisible();
  await page.unroute('**/api/today/scorecard');
  await page.route('**/api/today/scorecard', (r) => r.fulfill({ json: { rows: rows(0, 0).map((x) => ({ ...x, last_week: 0 })), reply_rate_percent: null, last_reply_rate_percent: null, winners_by_source: [], note: 'n' } }));
  await page.reload();
  await expect(page.getByText(/Nothing logged yet this week or last/)).toBeVisible();
  await expect(page.getByText('Reply rate')).toHaveCount(0);                                          // no emails sent, so no invented 0%
});
