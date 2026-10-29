# M08 - Front-end (MVP) and demo login

React + Vite + TypeScript in `frontend/`, using the prototype's own CSS (copied unchanged into `src/styles/prototype.css`)
so it looks the same. TanStack Query + Table, Chart.js. The login is the demo login from M07 (final login of the app).

## Data-source layer (`src/data/`)
All data and all actions go through one `DataSource` interface (`types.ts`); screens never call `fetch`.
- `live.ts` - the API (token in the `Authorization` header, a 401 signs the user out).
- `snapshot.ts` - placeholder for the demo edition (static JSON, M15); same contract.
- `index.ts` - picks one from `VITE_DATA_SOURCE` (`live` default, `snapshot`).
- Actions (`performAction`) go through the layer too; they answer "available in M09" until M09.

## Screens
- **Login** - calls `/api/health` the moment it opens and shows "Starting the server… (up to 30 s after idle)" until the API
  answers (retry every 3 s; after 90 s "Taking longer than usual…"). Form unlocks when the server is ready. Token in
  `sessionStorage`; expiry or 401 returns here with a message. With `VITE_LIVE_ENDED=true` it shows "The live system has
  ended" with a link to the demo edition (GitHub Pages root) and never calls the server.
- **Dashboard** - 5 KPI cards (count + USD; click filters by status), filters (dates, customer, region, company code
  1000-6000, status, classification; no mailbox filter), Performance Stability, Distribution across dimensions, Processing
  trend (month / quarter). Rows without an exchange rate are noted, never counted as 0.
- **Action Queue** - one row per invoice, server-side paging / sorting / filtering, column picker (remembered), new columns
  `Match_Field` + `Match_Level`, bulk select (only actions valid for every selected row are offered; "Confirm & Extract to
  Excel (n)"), row click opens the record.
- **Record Detail** (drawer) - original e-mail, attachment viewer (PDF pages as images via the signed link; extracted values
  highlighted from the evidence boxes), extracted fields, score breakdown (invoice match x0.35 ... confidence = max(fast
  path, formula)), BSID candidates, other rows of the same e-mail, role-aware action buttons, audit timeline.
- **Audit Trail** - filters + paging, details expandable. **Knowledge Base** - generated from the prototype with the agreed
  changes: "Invoice Number Match" (EXACT / NEAR / NONE), recalculated worked example (56.4 / 83.7 / 95.3 %), fast-path text
  "max(fast-path value, formula)", "Confirm & Extract to Excel", one inbox instead of three mailboxes.
- **Demo Control** - placeholder (M11).
- Live updates: `/api/changes` polled every 17 s **only while the tab is visible**; new rows reload the lists and show a toast.

## Backend changes in M08
- `/api/emails` (metadata) now needs the demo login (it listed real senders and subjects).
- `GET /api/attachments/{id}/page/{n}?token=` - a PDF page as PNG (110 dpi) for the viewer; link template is `page_url` in the
  record detail (signed, 5 minutes).
- CORS origins (Bicep parameter `corsOrigins`, `infra/main.parameters.json`): `https://process-intelligence1.github.io` and
  localhost only.

## Hosting: GitHub Pages
Workflow `.github/workflows/frontend.yml` tests, builds and publishes: root = `pages/` (landing, `privacy.html`, `terms.html`),
`/live/` = the live edition. The API address comes from the repository variable `API_BASE_URL` (never committed); the repository
variable `LIVE_ENDED=true` switches `/live/` to the "live system has ended" page. M15 adds the demo edition at the root.

## Tests
Front-end: 20 (Vitest + Testing Library): warm-up logic and login screen messages, sign-in / wrong code, live-ended page, data
layer (query strings, token, 401, signed links), evidence boxes, Action Queue columns / filters / bulk-action intersection /
"available in M09", column memory, Dashboard cards, change polling only while visible, Knowledge Base wording. Back-end: 563.

## Limits
- Actions are not functional yet (M09); the Confirm button is shown per role.
- Trend periods "date" and "week" of the prototype are not offered (the API gives months); month and quarter are.
- Evidence highlighting needs a position (`bbox`); values read from e-mail text or spreadsheets have none and are listed in the fields only.
