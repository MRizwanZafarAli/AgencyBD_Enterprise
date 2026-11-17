# QA report: AgencyBD, November 2026

What was tested, how, what was found, what was fixed, and what was **not** tested. Written to be read by the owner, not only by engineers.
Everything below was run on a copy of the app with throwaway data. Nothing touched real client data.

## 1. Bottom line
- The business workflow works end to end for every kind of user: sign in, find and check a prospect, draft, approve and send mail, receive a reply, honour opt-outs, win the client, see the weekly numbers.
- **QA found and fixed two serious security holes** (section 3). Both existed before this QA and neither came from the new features. If the app was ever reachable from outside your own computer or network before this fix, replace its secrets (section 6).
- Speed and stability are good for a small agency (section 4). Limits are listed plainly.
- Some test types cannot be done by one person at one computer. Section 7 says which, and why.

## 2. Test types: done, partly done, not done

| Test type | Status | What was done |
|---|---|---|
| Unit | Done | 800+ automated tests, plus the new ones from this QA |
| Integration | Done | Pieces tested together: sending with approval, webhooks, compliance, scoring |
| System / end to end | Done | A full business day as each kind of user (`tests/test_qa_business_day.py`) and 69 browser tests |
| Smoke | Done | Start, health, sign in, every screen loads |
| Sanity | Done | Each fix re-checked straight after it was made |
| Regression | Done | Whole suite re-run after every change |
| API / interface | Done | Every one of the 221 endpoints tried as 5 kinds of caller (`tests/test_qa_matrix.py`) |
| User acceptance (UAT) | Prepared | `docs/UAT_SCRIPT.md`, for real people to run and sign. Cannot be done by a robot |
| Component | Done | Modules tested alone (passwords, chase list, scorecard, partners, offers) |
| Performance | Done | Section 4 |
| Load | Done | Up to 100 people at once: all answered, most in under 140 ms |
| Stress | Done | Up to 800 at once with no failures; breaks at about 600+ simultaneous connections |
| Spike | Done | 800 at once after idle: zero failures, back to normal at once |
| Endurance / soak | Done | 3 minutes steady mixed traffic: memory flat, zero failures. (Longer runs, hours or days, were not done) |
| Scalability | Partly | One process only. See section 4 |
| Volume | Done | 50,000 clients, 200,000 notes: fast, after one fix |
| Usability | Partly | Screenshots reviewed by hand at three screen sizes and two themes; fixes made. Needs real users to finish |
| Compatibility | Partly | Chrome on desktop, tablet and phone sizes. **Firefox and Safari were not run** |
| Accessibility | Done | Automated check on every screen, both themes, desktop and phone, plus keyboard checks |
| Localization | Partly | Other alphabets, time zones, phone formats tested. **The screens are English only** |
| Globalization | Partly | 20 countries' mailing rules, half-hour time zones, clock changes. **Money is shown in dollars only** |
| Model accuracy | Done | The smart-search parser: 45 labelled searches, F1 0.97 after one fix |
| Data pipeline | Done | Backup and restore checked table by table; imports and webhooks tested |
| Bias and fairness | Done | Scores do not change with the name, language, address or phone country |
| Data drift | Not applicable | There is no trained model. The rules do not learn from data |
| Model security | Done | Injected instructions and a lying model cannot get an invented claim through |
| Mutation | Done | Section 5 |
| Basis path / statement / branch coverage | Done | Section 5 |
| Penetration | Partly | Hand-run attacks on the web server, sign-in and inputs. A professional test is still advised before public launch |
| Vulnerability scanning | Done | Code scanner, Python and JavaScript dependency audits |
| Security audit | Done | Section 3 |
| Disaster recovery | Done | Backup, restore, restart, forced crash |
| Failover | Not applicable | One server by design. There is no second server to switch to |
| Configuration | Done | Production start-up without secrets is refused; docs hidden in production |
| A/B | Done | Two kinds, see section 5 |
| Beta | Prepared | Plan in the UAT script. Needs outside users |
| Alpha | Prepared | Plan in the UAT script. Needs your team |
| Monkey | Done | About 800 random clicks, keys and hostile inputs across four tiers |
| Gorilla | Done | One feature repeated hard: 1,000 notes written at once by 40 people |
| Chaos | Partly | Forced crash mid-write, many writers, network down, read-only conditions. Real network failures between servers were not possible on one machine |
| Static testing | Done | Syntax, undefined names, unused code, types, lint |
| Dynamic testing | Done | Everything above that ran the code |
| White-box / black-box / gray-box | Done | Code-aware (coverage, mutation), user-style (UAT script, browser tests) and mixed (API sweeps) |
| Manual / automation | Done | Screenshots and attack tests by hand; everything else automated and kept in the repo |

## 3. Security findings
| # | Severity | Finding | Fixed |
|---|---|---|---|
| 1 | **Critical** | The web app's file server let anyone, without signing in, download any file on the machine, including the project's `.env` (which holds the secret that signs sessions) and `/etc/passwd`, using `//etc/passwd` or an encoded `../../.env`. | Yes. Only real, non-hidden files inside the web app's own folder are served. Tests added. |
| 2 | **Critical** | `POST /api/integrations/crm/hubspot` changed the pipeline stage of any client in any workspace with no sign-in and no signature check. | Yes. Needs a valid HubSpot v3 signature, a 5-minute window, and only changes this workspace's clients. |
| 3 | Medium | Outside RSS and XML feeds were parsed with a parser open to "XML bomb" attacks. | Yes (hardened parser). |
| 4 | Medium | No Content-Security-Policy or Permissions-Policy header was sent. | Yes. |
| 5 | Medium | The nginx file listens on plain HTTP only. Passwords would cross the network unencrypted. | **No. Needs a certificate and HTTPS in front of the app.** See section 6. |
| 6 | Low | A made-up country code was treated like a real one in the mailing rules. | Yes (blocked as unknown). |
| 7 | Low | A phone number starting `+0` was accepted. | Yes. |
| 8 | Low | The partner and saved-search limits could be exceeded by simultaneous requests. | Yes. |
| 9 | Info | Code scanner flags on SQL text building were checked one by one: all use fixed names and placeholders, so they are safe. | n/a |
| 10 | Info | Dependency audits: no known vulnerabilities in Python or JavaScript packages. | n/a |

## 4. Performance, capacity and recovery (one server process, a normal laptop)
| Measure | Result |
|---|---|
| Page load, first visit | about 0.6 s |
| Typical screen data at 100 people at once | 100 to 600 ms for the heaviest (Today), under 140 ms for most |
| 800 people arriving at once | 0 failures, slowest about 1.1 s, normal again immediately |
| Where it breaks | about 600+ simultaneous connections: some are refused, the server stays up |
| 3-minute soak | memory flat at 187 MB, open files flat, 0 failures |
| 50,000 clients, 200,000 notes, 30,000 jobs | every screen under 0.8 s after the pipeline fix |
| 40 people writing at once | 2,000 writes in 1.1 s, no database errors |
| Forced crash (kill -9) mid-write | database intact, every acknowledged write present |
| Backup of a 37 MB database | 0.3 s while the app runs; restore verified table by table; sign-in works on the copy |
| Five endpoints that wait on outside websites | 13 to 24 seconds when the internet is down (they time out). They should show a progress message and a stop button |

Scalability: the app is one process with one database file. A faster computer helps a little; more servers do not help, and running two copies of the app against one database would run the background workers twice (reminders could be sent twice). Run exactly one copy.

## 5. Quality of the tests themselves
- Coverage and mutation numbers: see section 8.
- Real A/B: the old gold design against the new teal design on readability (WCAG contrast). New is better in 6 of 10 pairs, the old gold button was stronger (9.9 against 5.5; both pass the 4.5 limit). Light and dark themes show no difference in errors, accessibility or speed. Which design people **prefer** needs real users.
- The app's own email A/B chooser was found to lock onto the worse variant in 23 to 72% of small runs. It is replaced and tested. It is also **not connected to sending yet**, so it never receives data. Connecting it is a feature to build.

## 6. What you should do now
1. **Replace the secrets** if the app was ever reachable from another computer, a server, or the internet before this fix: `python3 scripts/generate_secrets.py`, restart, and set passwords again with `python3 scripts/set_passwords.py`. Sessions will end. Also rotate any third-party keys that were stored in `.env`.
2. **Put HTTPS in front of the app** before anyone signs in over a network. Passwords must never cross it unencrypted.
3. **Run one copy** of the app.
4. Have **real people run** `docs/UAT_SCRIPT.md`.
5. Run the browser tests in Firefox and Safari before you promise those browsers.

## 7. Not tested, on purpose or by limit
- Firefox and Safari; real phones (only phone-sized screens in Chrome).
- Hours-long or days-long soak; traffic from many real internet locations; real network cuts between machines.
- Real mailboxes, real Telegram, WhatsApp, Twilio and ntfy accounts for sending (fakes used, except one live ntfy check earlier).
- Translated screens and other currencies (not supported).
- A professional penetration test and a legal review of the mailing rules.
- Whether real people like the design, or reply to the emails.

## 8. Numbers
| What | Result |
|---|---|
| Automated backend tests | **1,036 pass** (780 at the start of this QA, plus 256 new) |
| Browser tests (every screen, all four tiers, light and dark, accessibility) | **69 pass** |
| Endpoints exercised as 5 kinds of caller | 217 of 221 fully, 5 slow ones for sign-in and refusal only |
| Screens checked visually and by script | 174 combinations (4 tiers x 2 themes x 3 screen sizes x screens, plus every Settings section) |
| Console errors, failed requests, sideways scrolling, broken images, unnamed controls on those screens | **0** |
| Code coverage (lines and branches together) | **83%**. Highest: radar, compliance, proposals, auditors (96 to 99%). Lowest: the code that calls real AI models and outside vendors (34 to 41%), which cannot run offline |
| Mutation testing (deliberate breakages the tests must notice) | **53% caught at first, 79% after the new tests** (93 of 118). Lead scoring went from 6% to 87%. What still slips through is mostly small constants and wording |
| Code scanner (Bandit) | 1 high, 12 medium flags: all checked, 3 fixed (XML parser, hash flag, URL scheme), the SQL ones are safe by construction |
| Python and JavaScript package audits | No known vulnerabilities |
| Smart-search parser | Intent accuracy 45 of 45 labelled searches after one fix, F1 0.97, places 18 of 18 |
| Time-bomb check | One of my own tests depended on today's date and failed when the date moved. Fixed. Other new tests use fixed dates |

## 9. Files added by this QA
`tests/test_qa_matrix.py` (every endpoint x every caller), `test_qa_business_day.py` (a full day), `test_qa_input_safety.py` (hostile input, headers, pipeline limit),
`test_static_file_security.py`, `test_crm_webhook_security.py`, `test_qa_global.py`, `test_qa_nlp_accuracy.py`, `test_qa_fairness.py`, `test_qa_model_security.py`,
`test_qa_mutation_gaps.py`, `test_ab_selection.py`, and `docs/UAT_SCRIPT.md`.
The load, monkey and mutation robots were run from a scratch folder and are not part of the repository.
