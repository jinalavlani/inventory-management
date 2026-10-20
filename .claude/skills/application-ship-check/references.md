# Project References: Factory Inventory Management System

The project-specific map used by `SKILL.md`. To reuse this skill in another app, copy the folder and rewrite this file only. `SKILL.md` stays generic.

## Stack
- **Frontend:** Vue 3 (Composition API) + Vite + vue-router + axios, on port 3000.
- **Backend:** Python FastAPI + Pydantic + uvicorn, on port 8001 (Swagger docs at `/docs`).
- **Data:** JSON files loaded into memory at startup. There is no database and nothing is persisted.

## Entry files

### Frontend
| Purpose | File |
|---|---|
| App bootstrap and route table | `client/src/main.js` |
| App shell (nav, filter bar, tasks, profile, global styles) | `client/src/App.vue` |
| API client (all HTTP calls should go through here) | `client/src/api.js` |
| Shared filter state (singleton) | `client/src/composables/useFilters.js` |
| i18n and currency | `client/src/composables/useI18n.js`, `client/src/utils/currency.js` |
| Locale files (keys must match in both) | `client/src/locales/en.js`, `client/src/locales/ja.js` |
| Mock user / profile data | `client/src/composables/useAuth.js` |
| Pages | `client/src/views/*.vue` |
| Shared components and modals | `client/src/components/*.vue` |
| Build config | `client/vite.config.js`, `client/package.json` |

### Backend
| Purpose | File |
|---|---|
| App, CORS, Pydantic models, all routes, filter helpers | `server/main.py` |
| Data loading | `server/mock_data.py` |
| Data files | `server/data/*.json` |
| Data generator | `server/generate_data.py` |
| Dependencies | `server/pyproject.toml` |

### Tests
| Purpose | File |
|---|---|
| Fixtures (`TestClient`, imports `server/main.py`) | `tests/backend/conftest.py` |
| Test files | `tests/backend/test_*.py` |
| pytest config | `tests/pytest.ini` |

### Project rules
- `CLAUDE.md` (root), `client/CLAUDE.md`, `server/CLAUDE.md`

## Commands
```bash
# Backend tests (run from server/ so uv picks up server/.venv)
cd server && uv run pytest ../tests

# Frontend build check (there are no frontend tests or linter)
cd client && npm run build

# Run the app for visual checks
cd server && uv run python main.py      # http://localhost:8001
cd client && npm run dev                # http://localhost:3000
```

## Project-specific checks
- **Release standards (from `CLAUDE.md`):** test evidence before merging, no direct commits to `main`, and a one-line business impact summary in every PR.
- **Translations:** Every UI string goes through `t()`. Any new key must be added to both `en.js` and `ja.js`. Currency must follow the locale (USD/JPY) through the currency util.
- **Filters:** The four filters (period, location/warehouse, category, status) are shared across pages. `'all'` means no filter, and `api.js` drops it. Inventory has no month dimension. A filter change must behave the same on every page that uses it.
- **Contracts:** `api.js` already calls `/api/tasks` and `/api/purchase-orders`, which `main.py` doesn't implement. Don't count these as regressions caused by the change under review, but flag any new client call without a matching route. `Reports.vue` calls axios directly instead of `api.js`.
- **Models:** If a JSON data shape changes, update the matching Pydantic model in `main.py`, the fixtures in `conftest.py`, and any tests that check fields.
- **Security posture:** This is a demo. CORS allows all origins, there is no auth, and `useAuth.js` is a hardcoded mock. The repo is **public**, so flag any credentials, internal hostnames or private registry URLs. Leave `client/.npmrc` (public registry pin) and the gitignored `client/package-lock.json` as they are.
- **UI rules:** Use the slate/gray palette (`#0f172a`, `#64748b`, `#e2e8f0`), custom SVG charts, and CSS Grid. **No emojis in the UI.** In `v-for`, use unique keys (`sku`, `id`, `month`), never the index. Validate dates before calling `.getMonth()`.
