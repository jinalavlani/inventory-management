---
name: application-ship-check
description: Run a ship-ready review of a change before it is marked done, merged, or handed off. Checks scope and risk, UI consistency across pages (including translations), API contracts and error handling, security-sensitive areas (auth, PII, secrets), and produces concrete test ideas. Use when finishing a feature or fix, before opening or merging a PR, or when the user asks "is this ready to ship?"
---

# Application Ship Check

A structured, read-only review of a change before it is called done. It works on any app: it finds the change, reviews it against five areas, and ends with a clear verdict. It doesn't fix anything unless the user asks.

## Step 0: Establish context

1. **Load project references.** Read `references.md` in this skill's folder. It lists the app's entry files, conventions, and test commands. If it is missing or doesn't match this repo, find the equivalents yourself (see "Finding entry points" below) and use those.
2. **Identify the change under review.** In order of preference:
   - What the user named (a PR, branch, commit range, or files).
   - Otherwise, the current branch against its base: `git diff <base>...HEAD`, plus `git diff` and `git status` for uncommitted work. Find the base with `git merge-base HEAD origin/main` (or `master`/`develop`, whichever exists).
   - If there is no diff, say so and stop.
3. **Read the project's own rules.** Check `CLAUDE.md`, `CONTRIBUTING.md`, PR templates, and release or merge standards. Project rules override the generic checks below.

Read the full changed files, not just the diff hunks, when you need surrounding context. Follow callers and callees one level out.

## Step 1: Scope and risk assessment

- Summarize what changed in 2–4 sentences, in terms of user-visible behavior, not file names.
- List the changed files, grouped by layer: UI, client data/API layer, server routes, models/schemas, data/migrations, config, tests, docs.
- Flag **scope creep**: changes unrelated to the stated goal, drive-by refactors, formatting churn, and stray debug code (`console.log`, `print`, `debugger`, commented-out blocks, TODOs added by this change).
- Rate the risk as **Low**, **Medium** or **High**, with one line of reasoning. Raise the rating for:
  - Shared code paths: global state, layout/shell components, API clients, middleware, base models.
  - Data shape changes, migrations, or anything that is hard to roll back.
  - Auth, payments, permissions, or PII.
  - Changes with no tests touching them.
- Name the **blast radius**: which pages, endpoints, or consumers could break.

## Step 2: UI consistency across pages

Skip this step if the change touches no UI. Say so in the report.

- **Cross-page consistency:** If a pattern changed on one page (a filter, table, modal, empty or loading or error state, formatting helper), check the sibling pages that use the same pattern. List any page that now behaves or looks different.
- **Shared state:** If shared or global state changed (stores, composables, context, singletons), check every consumer, not just the page that was edited.
- **Translations / i18n:** If the app is localized:
  - Every new or changed user-facing string goes through the translation function. Flag any hardcoded strings.
  - Every new key exists in **every** locale file, at the same path. Diff the key sets, and don't assume the files match.
  - Removed keys aren't still referenced anywhere.
  - Numbers, dates and currency use the app's locale-aware formatters, not raw `toFixed` or string concatenation.
- **Design system:** The change uses existing colors, spacing, components and icons rather than one-off styles. Follow any project rules, such as "no emojis in UI" or a fixed palette.
- **States:** Loading, empty, error and long-content (overflow/truncation) states are handled.
- **Accessibility basics:** Interactive elements are real buttons or links, inputs have labels, images have alt text, and nothing relies on color alone.

## Step 3: API contracts and error handling

Skip this step if the change touches no API or data layer. Say so in the report.

- **Client ↔ server agreement:** For every endpoint the change adds, calls or modifies, confirm the path, HTTP method, query and body parameters, and response shape match on both sides. Grep the client for each call, and grep the server for its route. **Flag any call with no matching route** (it would return a 404) and any route field the client reads but the server never sends.
- **Schema changes:** If a response or request model changed, check every consumer: frontend code, other endpoints, tests, fixtures and seed data. Removing or renaming a field is a breaking change, so call it out.
- **Validation:** Inputs are validated at the boundary, including types, required fields, ranges and enum values. Check how sentinel values (such as `'all'`, empty string or `null`) are handled.
- **Error paths:**
  - The server returns correct status codes (404 for a missing resource, 400/422 for bad input, not a 200 with an error body or an unhandled 500).
  - The client catches failures, shows the user a message, and doesn't leave the UI stuck loading.
  - Errors don't leak stack traces or internal details to the client.
- **Hardcoded config:** Look for base URLs, ports, or environment-specific values added inline instead of through config.
- **Performance smells:** N+1 calls, unbounded lists with no pagination, repeated identical requests, or heavy work on every request.

## Step 4: Security-sensitive areas

Always run this step, even if the change looks unrelated. Report "nothing sensitive touched" if that is true.

- **Auth and authorization:** Any new endpoint or page is protected the same way as its neighbors. Check for missing permission checks, trust in client-supplied user IDs or roles, and auth bypass for convenience.
- **PII and sensitive data:** Emails, phone numbers, addresses, names, financial data and IDs must not be:
  - logged, put in URLs or query strings, or sent to analytics or third parties;
  - returned in API responses that don't need them;
  - stored in `localStorage` or `sessionStorage` without a reason.
- **Secrets:** No API keys, tokens, passwords, internal hostnames or private registry URLs in code, config, fixtures, tests or docs. Check `.env*` files and lockfiles in the diff. Confirm `.gitignore` still covers secret-bearing files.
- **Injection and unsafe rendering:** User input is not interpolated into SQL, shell commands, file paths or HTML. Look for `v-html`, `dangerouslySetInnerHTML`, `innerHTML`, `eval`, f-string SQL and `subprocess` with `shell=True`.
- **CORS, headers and cookies:** Flag new wildcard origins, credentials combined with wildcards, and cookies without `HttpOnly`/`Secure`/`SameSite`.
- **Dependencies:** For any new or upgraded package, check that it is well known, pinned appropriately, and pulled from the public registry the project expects.

## Step 5: Concrete test ideas

Write tests specific to this change, not generic advice. For each idea, give:
- **Type:** unit, API/integration, end-to-end/browser, or manual.
- **Setup:** the exact inputs, filter values, locale, user, or data state.
- **Expected result:** a specific, checkable outcome.

Cover:
- The **happy path** for each new behavior.
- **Edge cases:** empty data, a single item, boundary values, sentinel values (`'all'`, `null`, `''`), very long strings, and non-default locales.
- **Error cases:** a missing resource, invalid input, and a server failure as seen from the UI.
- **Regression checks** for the blast radius named in Step 1.

Then **run the existing test suite** with the command in `references.md` (or the project's documented command) and report the actual pass/fail counts. If tests can't be run, say why. Don't claim they pass. If the change has UI and a running app or browser tool is available, suggest (or perform, if asked) a quick visual check of the affected pages.

## Report format

End with this report. Keep it scannable, and cite `file:line` for every finding.

```markdown
## Ship Check: <short change description>

**Verdict:** SHIP | SHIP WITH NOTES | BLOCK
**Risk:** Low | Medium | High — <one-line reason>
**Scope:** <2–4 sentence summary> · Blast radius: <pages/endpoints>

### Blocking issues
- <file:line> — <issue> — <why it blocks> — <suggested fix>

### Should fix before merge
- ...

### Nice to have
- ...

### Area results
| Area | Result | Notes |
|---|---|---|
| Scope & risk | ✅ / ⚠️ / ❌ | |
| UI consistency & i18n | ✅ / ⚠️ / ❌ / N/A | |
| API contracts & errors | ✅ / ⚠️ / ❌ / N/A | |
| Security & PII | ✅ / ⚠️ / ❌ | |
| Tests | ✅ / ⚠️ / ❌ | <suite result: X passed / Y failed> |

### Test ideas
1. [type] <setup> → <expected result>

### Release checklist
- [ ] Test evidence attached
- [ ] <project-specific release rules from CLAUDE.md, e.g. PR business-impact line>
```

**Verdict rules:**
- **BLOCK** for a failing test suite, a broken client↔server contract, a leaked secret or PII, an auth gap, a missing translation key in a shipped locale, or a violation of a mandatory project rule.
- **SHIP WITH NOTES** when only should-fix or nice-to-have items remain.
- **SHIP** when nothing material was found and the tests pass.
- Don't soften a BLOCK. If you are unsure whether something is a real problem, list it under "Should fix" and say what would confirm it.

## Finding entry points (when references.md is missing)

Find the equivalents of the files `references.md` would list:
- **Manifests:** `package.json`, `pyproject.toml`, `requirements.txt`, `go.mod`, `Cargo.toml`, `pom.xml`, `Gemfile`.
- **Frontend entry and routing:** `main.*`, `index.*`, `App.*`, router config, and `pages/` or `views/` directories.
- **API client:** files named `api.*`, `client.*` or `services/`, or code that wraps `fetch` or `axios`.
- **Server entry and routes:** `main.py`, `app.py`, `server.*`, `routes/`, `controllers/`, `urls.py`.
- **Models and schemas:** `models.*`, `schemas.*`, ORM definitions, OpenAPI specs.
- **i18n:** `locales/`, `i18n/`, `translations/`, `messages/`.
- **Auth:** files or folders named `auth`, `session`, `middleware`, `guard` or `permissions`.
- **Tests:** `tests/`, `__tests__/`, `*.test.*`, `*_test.*`, `spec/`, plus the test command from the manifest or README.

Mention in the report that `references.md` should be filled in for this project.
