# Contributing to AgencyBD

This is proprietary software owned by Future Builders (see `LICENSE`). Only people the Owner has engaged or approved may contribute.

## Who owns what you write
By opening a pull request or pushing a commit you confirm that:

1. **You wrote it yourself**, or you have the right to contribute it. You did not copy code from a project whose license does not allow that, from a former employer, or from a client.
2. **It belongs to the Owner.** All rights in your contribution are assigned to Future Builders. If the law of your country does not allow assigning them, you grant the Owner an exclusive, worldwide, perpetual, irrevocable, royalty-free license to use, change, sublicense and sell it, with no further payment.
3. **You keep no right to reuse it** in a way that competes with the Owner. You may still use your general skills and knowledge.
4. If your contract with the Owner (employment or contractor agreement) says more, that contract also applies.

Contractors and volunteers without a signed agreement should send the Owner a short written confirmation of points 1 to 3 before their first pull request is merged.

## Rules for every change
- **Never commit secrets**: passwords, API keys, tokens, `.env` files, real customer data or databases. Sign-in passwords are set with `python scripts/set_passwords.py` and are never stored in the repository.
- **Never invent data.** The app must not show a number, contact, price, website or result that was not measured or typed by a person. Anything unknown stays blank or says it is unknown.
- **Branch and review**: work on a branch such as `feature/short-name`, open a pull request into `main`, and get it reviewed. Do not push directly to `main`.
- **Tests must pass** before a pull request is merged:
  - backend: `python3 -m pytest -q`
  - browser and accessibility: `./scripts/e2e.sh`
  - front end: `cd frontend && npm run lint && npm run build`
- **Add a test with every fix or feature**, and keep the wording of messages in plain language.
- **Do not add third-party code or assets** (fonts, images, templates, snippets) without checking their license allows commercial use, and say where they came from in the pull request.
- **Keep it private.** Do not paste source code or customer data into public tools.

## Security problems
Do not open a public issue. Tell the Owner directly.
