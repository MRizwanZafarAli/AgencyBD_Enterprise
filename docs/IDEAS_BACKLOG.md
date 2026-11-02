# Ideas backlog: what is left to build or try

Ranked by "most likely to bring a client soon" first. Everything here is free to run unless it says otherwise.
**Checked** means a web search in November 2026 supported it. **Unchecked** means it is my own reasoning and needs a quick look before building.
Rules that never change: no logged-in scraping of other people's sites, no invented data, one honest message per person.

## Already built
Site Clinic and teardown, Find (local, jobs, tenders), Alert Desk (client message to phone, reminders, calls), and from this round:

| Idea | Where it lives | Notes |
|---|---|---|
| Lead Finder watches | Find, tab Watching | New UK companies (free key), **new Irish companies (no key, live-tested)**, jobs that match your words, problems on sites you checked. Alerts only on new things. |
| Daily re-check of your saved sites | Runs by itself; shows in Today | Reports a new certificate problem, lost HTTPS, a new vulnerability match, or a site down on two checks in a row. A site that blocks robots is never called down. |
| Chase today | Clients, Pipeline; Today focus | Clients in Proposal, Meeting or Outreach stages that went quiet with no follow-up planned. One tap sets a follow-up date. |
| Fixed-price offer | Tools, Site Clinic, button Offer | Built from the measured findings and your own prices. Prices and dates you did not set stay blank and are listed. |
| Booking link in every message | Settings, Agency profile | Was already used in email drafts, replies and proposals. Now also in the offer and the reply drafts. |
| Reply helper | Channels, Client messages, Draft a reply | Three short drafts from your own settings. No AI key needed. States a price only if you set one. |
| Partner tracker | Clients, Partners | Who, what you offered, referrals each way, and who needs a nudge. |
| Weekly scorecard | Today, Your week | This week against last week, counted from real records. Rates only when there is something to divide by. Shows where won clients came from. |
| Review request after a win | Automatic task when a client moves to Won | One task a week later: ask for a review and one introduction. |
| Where else to look | Find, Watching | Official portals with no feed we may read (Pakistan tenders, P@SHA, PSEB, UN, ReliefWeb). Links only. |

## 1. What is still open

| Idea | Status |
|---|---|
| Pakistan tenders as a feed | **Not built on purpose.** PPRA publishes no feed we may read; the tools that exist scrape the portals and may break their terms. Use the links in "Where else to look". |
| US state new business filings | Not built. Each state differs and the search found no usable open feed. |
| Product Hunt and BetaList launches | Not built. Needs a free token and terms check; a new launch is a weak sign that a web agency is needed. |
| Expired or soon-expiring domains | Not built. No public registry data that is simple and reliable. |
| Funding news and change of owner | Not built. Matching a news item to a website needs care to avoid wrong matches. |
| Public "check my website" page | Not built. A public page that examines other people's sites on demand needs abuse limits and a privacy notice first. The one-page report you send yourself exists in Tools. |
| AI polish for reply drafts | Optional. The drafts work without it; with a model key they could sound more personal. |

## 2. Sources checked while building

- **Companies House** (UK): built. Needs your free key.
- **CRO** (Ireland): built. The open data search interface refuses queries that use certain SQL words, so the search uses only plain conditions.
- **Hacker News**: the "Who is hiring" thread is already read. The "Freelancer? Seeking freelancer?" thread is no longer published, so I removed it from this list.
- **r/forhire**: already read through its public feed.
- **WordPress and server versions**: the Site Clinic already matches them to known vulnerabilities, and Lead Finder can watch for that.

## 3. Ways to get clients that need no code

Checked in general guides (anecdotal, many from vendors, so treat the percentages in the playbook as rough):
- A narrow offer beats "web developer". Pick two niches (for example dental clinics and law firms) and make one page for each.
- Referrals and partners beat cold messages for margin. Accountants, bookkeepers, lawyers and business associations meet owners before they think about a website.
- Outbound works best with a visible trigger (a broken site, a new company), not just "small business".
- Marketplaces are for starting. Many freelancers drop them once referrals and outbound work.
- Warm up LinkedIn contacts by commenting before you ask.

Unchecked but cheap to try:
1. A free "website health check" page you link from your profile and email signature.
2. A one-page PDF of what you found, left with a business in person or sent by email.
3. Offer a fixed-price 48-hour fix for one problem, such as an expired certificate.
4. Ask each past client for one named referral and one review.
5. Local meetups, university alumni groups, coworking spaces, chambers of commerce.
6. Answer questions in r/webdev, r/smallbusiness and Stack Overflow with real help and a link to your work.
7. A tiny open-source tool or template with "built by Future Builders".
8. Write one local guide: "What a dentist's website needs in Dublin".
9. Join one or two free business directories in each country you target.
10. Offer white-label work to agencies that sell websites but do not build them.
11. Track which play brings each client, and drop what did not.
12. Re-contact old colleagues, classmates and past clients with a plain one-line update.

## 4. Things I will not build, and why

- Logging into Fiverr, Upwork or LinkedIn for you, or reading their inboxes with a robot: bans accounts and stores your passwords.
- Automatic connection requests, comments or direct messages: same reason.
- Messaging strangers on WhatsApp or SMS: fastest way to lose a number.
- Guessing emails and sending to them: you would be emailing people who never published an address, and bounces damage your domain.
- Identifying companies from the IP addresses of people who visit your site: inaccurate and needs a privacy notice in the EU. The visitor tracker added in the earlier commits needs a review for this.
- Buying lead lists or scraping paid databases.

## 5. Honest limits of this research

The searches were light. They confirmed the Companies House search parameters and the Irish open data file. They did not confirm Companies House's current rate limit, Product Hunt's current terms, or free sources for the US, Pakistan, domain expiry or WordPress versions. Verify each before relying on it.
