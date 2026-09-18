# DPI-LS_IMPLEMENTATION_PLAN

## A. COMPLETED
- Initial project structure (FastAPI, SQLite, Vanilla JS)
- Base engine calculation (engine/score.py) and telemetry observation schema
- 300 baseline unit/integration tests
- Onboarding POST endpoint (partially)

## B. PARTIALLY COMPLETED
- Onboarding (Needs duplicate error handling UI)
- Configuration (Needs dynamic single-source-of-truth live preview instead of JS Math.pow)
- Dashboard/Rating/Profile (Currently fetch from DB, but rely on statically/manually inserted telemetry rather than dynamic execution flow)

## C. BROKEN
- None that break the baseline, but the "E2E flow" is broken because execution is stubbed and configuration isn't linked to scoring.

## D. MISSING
- Proper Execution Backend (an ExecutionRow DB table, async execution wrapper, timeout, audit)
- Live Score Preview endpoint GET /agents/{agent_id}/score/preview
- Real MCP connection health check (currently stubbed)
- True telemetry flow from UI -> Config -> Execute -> Telemetry -> Dashboard

## E. NEEDS REFACTORING
- widget/agent-config.html: Remove ase_dpi calculation.
- widget/dpi-ls.js: Remove all independent math.

## F. PRODUCTION BLOCKERS
- Browser calling mock/stub execution which freezes the server synchronously.
- Hardcoded localhost endpoints.
- Inability to securely manage vendor credentials.

## G. FILES TO MODIFY
- pi/app.py
- store/models.py
- widget/agent-config.html
- widget/dpi-ls.js

## H. FILES NOT TO MODIFY
- engine/score.py (Unless resolving the formula conflict if required by the user, but we will leave the composite logic as the approved source of truth)
- Existing passing tests.

## I. DATABASE CHANGES
- Add ExecutionRow to store/models.py.

## J. API CHANGES
- Add GET /api/agents/{agent_id}/score/preview
- Refactor POST /api/agents/{agent_id}/execute to async/background task with DB persistence.

## K. FRONTEND CHANGES
- Strip Math.pow and Math.random
- Wire config page live projection to the preview API.

## L. MCP CHANGES
- Add basic connection test endpoint for UI.

## M. SCORING CHANGES
- Ensure all screens (Dashboard, Rating, Profile) call the same score output API.

## N. TEST PLAN
- Run uv run pytest to ensure baseline stays green.
- Perform a manual browser E2E test.
