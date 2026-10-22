# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

Factory Inventory Management System Demo with GitHub integration - Full-stack application with Vue 3 frontend, Python FastAPI backend, and in-memory mock data (no database).

> ⚠️ **This repository and any fork you create are PUBLIC.** Do not commit credentials, internal hostnames, or private registry URLs. `client/.npmrc` pins the public npm registry and `client/package-lock.json` is gitignored to prevent locally-configured registries from leaking into commits — leave both in place.

## Critical Tool Usage Rules

### Subagents
Use the Task tool with these specialized subagents for appropriate tasks:

- **vue-expert**: Use for Vue 3 frontend features, UI components, styling, and client-side functionality
  - Examples: Creating components, fixing reactivity issues, performance optimization, complex state management
  - **MANDATORY RULE: ANY time you need to create or significantly modify a .vue file, you MUST delegate to vue-expert**
- **code-reviewer**: Use after writing significant code to review quality and best practices
- **Explore**: Use for understanding codebase structure, searching for patterns, or answering questions about how components work
- **general-purpose**: Use for complex multi-step tasks or when other agents don't fit

### Skills
- **backend-api-test** skill: Use when writing or modifying tests in `tests/backend` directory with pytest and FastAPI TestClient

### MCP Tools
- **ALWAYS use GitHub MCP tools** (`mcp__github__*`) for ALL GitHub operations
  - Exception: Local branches only - use `git checkout -b` instead of `mcp__github__create_branch`
- **ALWAYS use Playwright MCP tools** (`mcp__playwright__*`) for browser testing
  - Test against: `http://localhost:3000` (frontend), `http://localhost:8001` (API)

## Release Standards
- **Test evidence before merging:** Every change needs test evidence before it is merged, such as passing `cd server && uv run pytest ../tests` output or Playwright verification for UI changes. Include that evidence in the PR.
- **No direct commits to `main`:** Work on a feature branch and merge through a PR.
- **Business impact summary:** Every PR description must include a one-line business impact summary.

## Stack
- **Frontend**: Vue 3 + Composition API + Vite (port 3000)
- **Backend**: Python FastAPI (port 8001)
- **Data**: JSON files in `server/data/` loaded via `server/mock_data.py`

## Commands

```bash
# Backend (http://localhost:8001, docs at /docs)
cd server && uv sync && uv run python main.py

# Frontend (http://localhost:3000)
cd client && npm install && npm run dev
cd client && npm run build          # production build -> client/dist/

# Backend tests — run from server/ so uv uses server/.venv (pytest is a uv dev dependency).
# `cd tests && uv run pytest` does NOT work: tests/ has no pyproject, so pytest isn't found.
cd server && uv run pytest ../tests
cd server && uv run pytest ../tests/backend/test_inventory.py::TestInventoryEndpoints::test_get_all_inventory
```

- `scripts/start.sh` / `scripts/stop.sh` start/stop both servers on macOS/Linux only; on Windows run the two servers manually.
- No linter, formatter, or frontend test suite is configured.
- `uv.lock` and `*.lock` are gitignored.

## Architecture Notes

- **Backend is a single file.** All Pydantic models and routes live in `server/main.py`. `server/mock_data.py` loads `server/data/*.json` once at import time into module-level lists, and routes filter those lists in memory. Nothing is persisted. `server/generate_data.py` regenerates the JSON.
- **Filtering:** `apply_filters()` handles `warehouse`/`category`/`status` (`'all'` or missing means no filter). `filter_by_month()` substring-matches `order_date` against a month like `2025-03`, or expands `Q1-2025`…`Q4-2025` via `QUARTER_MAP`.
- **Frontend filter state:** `client/src/composables/useFilters.js` holds module-level singleton refs shared by every view. `getCurrentFilters()` maps `selectedLocation` to `warehouse` and `selectedPeriod` to `month`. `client/src/api.js` drops any param equal to `'all'`. The API base URL `http://localhost:8001/api` is hardcoded in `api.js`, and there is no Vite proxy.
- **i18n/currency:** All UI strings go through `useI18n().t('dot.path')` with `client/src/locales/en.js` and `ja.js`, so add keys to both. The locale persists in `localStorage` (`app-locale`), and currency follows it (en→USD, ja→JPY; see `client/src/utils/currency.js`).
- **Mock user:** `useAuth.js` is a hardcoded, locale-aware mock user with no real auth.
- **Tests:** `tests/backend/conftest.py` puts `server/` on `sys.path` and imports `main.app` into a `TestClient` fixture. Tests assert against the real JSON data.

### Known frontend/backend gaps
- `api.js` calls `/api/tasks` (GET/POST/PATCH/DELETE) and `/api/purchase-orders` (GET/POST), but **`main.py` doesn't implement them**. `App.vue` calls `getTasks()` on load and gets a 404. `purchase_orders` data is loaded but only used for the `has_purchase_order` flag on `/api/backlog`.
- `client/src/views/Backlog.vue` exists but has no route in `client/src/main.js`.
- `tests/README.md` and the `backend-api-test` skill mention `test_orders.py` and 51 tests. That file doesn't exist, and the suite currently has 40 tests.

## Key Patterns

**Filter System**: 4 filters (Time Period, Warehouse, Category, Order Status) apply to all data via query params
**Data Flow**: Vue filters → `client/src/api.js` → FastAPI → In-memory filtering → Pydantic validation → Computed properties
**Reactivity**: Raw data in refs (`allOrders`, `inventoryItems`), derived data in computed properties

## API Endpoints
- `GET /api/inventory` - Filters: warehouse, category
- `GET /api/orders` - Filters: warehouse, category, status, month
- `GET /api/dashboard/summary` - All filters
- `GET /api/demand`, `/api/backlog` - No filters
- `GET /api/spending/*` - Summary, monthly, categories, transactions
- `GET /api/inventory/{id}`, `/api/orders/{id}` - Single item (404 if missing)
- `GET /api/reports/quarterly`, `/api/reports/monthly-trends` - Aggregates computed from orders
- `GET /api/restock/recommendations?budget=` - Greedy budget fill over demand forecasts (increasing trend first, then by growth); uses `unit_cost`/`lead_time_days` from `demand_forecasts.json`
- `GET|POST /api/restock/orders` - Submitted restock orders (in-memory list; server recomputes prices; lead time = longest item's)

## Common Issues
1. Use unique keys in v-for (not `index`) - use `sku`, `month`, etc.
2. Validate dates before `.getMonth()` calls
3. Update Pydantic models when changing JSON data structure
4. Inventory filters don't support month (no time dimension)
5. Revenue goals: $800K/month single, $9.6M YTD all months

## File Locations
- Views: `client/src/views/*.vue`
- API Client: `client/src/api.js`
- Backend: `server/main.py`, `server/mock_data.py`
- Data: `server/data/*.json`
- Styles: `client/src/App.vue`

## Design System
- Colors: Slate/gray (#0f172a, #64748b, #e2e8f0)
- Status: green/blue/yellow/red
- Charts: Custom SVG, CSS Grid for layouts
- No emojis in UI
