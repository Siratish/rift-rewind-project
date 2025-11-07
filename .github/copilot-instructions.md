## Quick orientation

This repo hosts a single-page React app in `frontend/` (Vite-based). It implements the "Rift Trivia" UI with three routes: `/` (Landing), `/progress`, `/insights`. The app is client-only and talks to an external HTTP API and an optional WebSocket backend.

## How to run (developer workflows)
- From `frontend/`:
  - Dev server: `npm run dev`
  - Build: `npm run build` (output in `dist/`); Preview: `npm run preview`
  - Lint: `npm run lint`

## Architecture & data flow
- Routing and transitions: `src/App.jsx` uses `react-router-dom@7` with `BrowserRouter` and `framer-motion` page animations (special “zoom” transition from `/progress` → `/insights`).
- API calls: `src/api.jsx` exports `fetchSummoner(riotId, region)` which POSTs JSON to `API_BASE` and expects a JSON body.
- Env config: `src/config.jsx` reads either Vite or CRA-style envs: `VITE_API_BASE`/`REACT_APP_API_BASE` and `VITE_WS_URL`/`REACT_APP_WS_URL`.
- WebSocket: `src/hooks/useWebSocket.jsx` reads `WS_URL`, opens a `WebSocket`, parses only JSON messages, and returns `{ connected, send }` where `send` JSON.stringify’s the payload and returns `false` if not open.
- Cross-page state: `sessionStorage` is used:
  - `rr_summoner_response` (Landing → Progress)
  - `rr_final` (Progress → Insights)

## Contracts that components rely on
- `fetchSummoner` request: `{ riotId, region }`.
- Expected response shape (used across pages): `{ summoner, routing_value, year, summary_exists, final_exists }`.
- Progress → backend: on WS open, Progress sends `{ action: 'startJob', puuid, year, summary_exists, final_exists, routing_value }`.
- WS messages handled in Progress: `START_RETRIEVE_MATCH`, `RETRIEVING_MATCH` with `{count,total}`, `PROCESSING_MATCH`, `GENERATING_FACTS`, and `COMPLETE` with `{ result: [...] }` which becomes `rr_final` as `{ quizFacts, summoner }`.

## Dev and demo tips specific to this app
- Demo mode: entering `strawberryseraphine#main` on Landing navigates to `/progress?demo=true` and simulates WS updates (see `ProgressPage.jsx`). Use this for UI/dev without a backend.
- Styling primitives live in `src/index.css` via Tailwind v4 utilities. Prefer existing utilities: `rr-panel`, `btn-cta`, `riot-gold`, `progress-track`, `progress-fill`, `rr-spinner`, `rr-particles`.
- Image export: `ShareCardPreview.jsx` dynamically imports `html-to-image` to download a share card PNG.

## Integration points and env
- Set `VITE_API_BASE` and `VITE_WS_URL` in a `.env` (Vite) or use CRA-style `REACT_APP_*`—both are supported by `config.jsx`.
- Public assets (e.g., default icons) should be placed under `frontend/public/` and referenced by path.

## Making changes safely
- Keep `sessionStorage` keys (`rr_summoner_response`, `rr_final`) stable or update all writers/readers (`LandingPage.jsx`, `ProgressPage.jsx`, `InsightsPage.jsx`).
- Preserve `send`’s boolean return contract in `useWebSocket.jsx` and its JSON-only semantics (invalid payloads are warned and dropped).
- Maintain API error behavior in `fetchSummoner`: non-JSON errors fall back to `'Unknown error'`; UI shows `err.message`.

## Pointers to key files
- `frontend/vite.config.js` — plugins (React Compiler, Tailwind v4)
- `frontend/src/api.jsx` — HTTP contract
- `frontend/src/config.jsx` — env resolution
- `frontend/src/hooks/useWebSocket.jsx` — WS plumbing
- `frontend/src/App.jsx` — routes + transitions
- `frontend/src/components/*` — page flows and UI (Landing/Progress/Insights)

If anything here is unclear or you want more details (e.g., example WS message, adding a new route, or expanding demo data), tell me which area to expand and I’ll iterate.
