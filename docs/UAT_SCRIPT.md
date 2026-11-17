# User acceptance test script (UAT)

For real people to sign off the product before it is used with real prospects. Automated tests prove the rules; only you can say whether it
is the right tool for your work. Run it on a copy of the database, not on live client data. Tick each box, write what you saw, and note the date.

Set up once (about 10 minutes)
- [ ] The app starts at http://localhost:8001 and the sign-in page shows four tiers.
- [ ] `python3 scripts/set_passwords.py` has set a different password for each tier.
- [ ] In Settings > Agency profile you entered your real name, agency name, postal address and public address.
- [ ] In Settings > Services and proof you entered a price for at least one service and one real piece of proof (or left proof empty).

How to record a problem: screen, what you did, what you expected, what happened, a screenshot.

## A. Owner (Super admin)
| # | Do this | You should see | Pass | Notes |
|---|---|---|---|---|
| A1 | Sign in as Super admin | Today opens with a greeting, then your dashboard | [ ] | |
| A2 | Settings > Access and passwords > change the Auditor password to something new | "Password for Auditor changed"; the old password no longer works | [ ] | |
| A3 | Try to give two tiers the same password | A clear message that every tier needs its own | [ ] | |
| A4 | Settings > Message alerts > fill Telegram or ntfy > press the test button | A real message arrives on your phone | [ ] | |
| A5 | Settings > Integrations and keys > save a key | It shows masked ("••••1234") and never again in full | [ ] | |
| A6 | Press "Stop sending" in the top bar, then resume | A red banner appears, then goes away | [ ] | |
| A7 | Settings > Data and export > export | A file opens in a spreadsheet with readable text, also for non-English names | [ ] | |

## B. Growth lead
| # | Do this | You should see | Pass | Notes |
|---|---|---|---|---|
| B1 | Sign in as Growth lead | No Settings item in the menu | [ ] | |
| B2 | Find > Local businesses: "dentists in [your city]" | Real businesses, each with a reason it was ranked; nothing invented | [ ] | |
| B3 | Find > Watching > New watch (jobs with your skills) | It saves, looks once, and later tells you only about new items | [ ] | |
| B4 | Open a client > run the website check > read the teardown | Findings that you can check by opening the site yourself | [ ] | |
| B5 | Site Clinic > Offer | A one-page offer; prices you did not set are blank and listed | [ ] | |
| B6 | Write the first email to someone you know | It waits for approval; nothing is sent before you approve | [ ] | |
| B7 | Approve it, then send | It arrives with your address and an unsubscribe link | [ ] | |
| B8 | Click the unsubscribe link in that email | A confirmation page; afterwards that address cannot be emailed | [ ] | |
| B9 | Move a client to Won | A task appears to ask for a review a week later | [ ] | |
| B10 | Today > "Your week" | Numbers match what you did; no invented percentages | [ ] | |

## C. Sales rep
| # | Do this | You should see | Pass | Notes |
|---|---|---|---|---|
| C1 | Sign in as Sales rep | Find, Clients, Channels, Tools; no Settings | [ ] | |
| C2 | Add a prospect by hand and run its check | Findings appear; no price or contact is invented | [ ] | |
| C3 | Try to send an email | It is refused; a Growth lead must approve | [ ] | |
| C4 | Channels > Client messages > Add by hand > Draft a reply | Three drafts; a price only if you set one | [ ] | |
| C5 | Clients > Chase today | Quiet clients listed with the reason; "Tomorrow" sets a follow-up | [ ] | |
| C6 | Clients > Partners > add one, log contact and a referral | Counts and reminders update | [ ] | |

## D. Auditor (read only)
| # | Do this | You should see | Pass | Notes |
|---|---|---|---|---|
| D1 | Sign in as Auditor | Only Today, Clients and Tools | [ ] | |
| D2 | Look at the audit trail and the suppression list lookup | Readable; the opt-out list says who is blocked | [ ] | |
| D3 | Try to change a stage, add a partner or run a check | Refused with a plain message | [ ] | |

## E. Everyone
| # | Do this | You should see | Pass | Notes |
|---|---|---|---|---|
| E1 | Use it on your phone (open the address on the same network) | Nothing runs off the screen; buttons are easy to tap | [ ] | |
| E2 | Switch to dark mode and back | Both are readable | [ ] | |
| E3 | Type something odd in a box (quotes, emoji, Urdu or Arabic) | It is saved and shown as typed | [ ] | |
| E4 | Leave a tab open for 12 hours, or change your tier's password | You are asked to sign in again, and nothing is lost | [ ] | |
| E5 | Honesty check: does any number, name, price or promise look made up? | None. If one does, write it down | [ ] | |

## Sign-off
Name: ______________  Role: ______________  Date: ____________
[ ] Accepted  [ ] Accepted with the notes above  [ ] Not accepted

## Beta and alpha testing
- Alpha: your own team uses it for one week on real (non-client) data, then reports with the form above.
- Beta: give two or three friendly agency owners a separate copy and their own passwords, for two weeks. Ask them the questions in E5 and "What did you expect that was missing?".
