# M07 - Workbench API

Everything the screens need, plus the backend half of the demo login (which is the final login of the app).

## Login (`app/api/auth.py`)
- `GET /api/auth/demo-users` - the four demo users. `POST /api/auth/demo-login {user, access_code}` -> token. `GET /api/auth/me`.
- The access code (`DEMO_ACCESS_CODE`) and the signing key (`JWT_SECRET`) are Key Vault secrets `demo-access-code` and
  `jwt-secret`. Empty = login off (503), no token, no data.
- Token lasts 10 hours (`TOKEN_HOURS`); after that every call answers 401 "Token expired".
- Rate limit: 10 attempts per minute per IP, then a 2-minute lockout (429 + `Retry-After`). The counter lives in memory
  (one API replica; a restart clears it). Wrong user and wrong code give the same 401.
- `LOGIN_OK`, `LOGIN_FAILED` and `LOGIN_BLOCKED` (once per lockout) go to `ar.audit_log` with IP and user - never the code.

## Data endpoints (all need `Authorization: Bearer <token>`)
| Endpoint | What |
|---|---|
| `GET /api/work-items` | Action Queue. Filters: `from_date`, `to_date` (e-mail date), `classification`, `bsid_match`, `status`, `decision`, `min_confidence`, `max_confidence`, `customer` (number or name), `company_code`, `region`, `q`; `sort`, `order`, `page`, `page_size` (max 200). Each row has `amount_usd`, `usd_status` and `allowed_actions`. |
| `GET /api/work-items/{id or ENT-...}` | Record Detail: e-mail, attachments with signed links, classification, extraction + evidence, candidates with BSID item data, score breakdown, same-e-mail items, PTP commitments, audit trail, `allowed_actions`. |
| `GET /api/attachments/{id}/file?token=` | The file. Signed link (about 5 minutes, tied to that attachment id), so a browser PDF / image viewer needs no header. HTML / SVG / unknown types are only ever downloaded. |
| `GET /api/attachments/{id}/layout` | Words with positions and tables (evidence highlighting). |
| `GET /api/kpis` | Dashboard: KPI cards (count + USD), distributions (customer top 10, region, company code, classification, status), monthly trend, performance stability (daily auto rate + average confidence). Same filters as the list. |
| `GET /api/audit` | Audit Trail with filters (`from_date`, `to_date`, `actor`, `action`, `entity_type`, `entity_id`, `q`). |
| `GET /api/changes?since=` | What is new / updated since a time (counts + ids). The front-end polls it every 15-20 s while the tab is visible and uses `next_since` (server time minus 60 s, so rows of a slow transaction are not missed). **No Server-Sent Events**: an open connection would keep the Container App awake. |

`/api/emails` (metadata only) and `/api/admin/*` (admin key) are unchanged.

## USD conversion (`app/fx.py`)
Latest `sap.tcurr` rate (type M, to USD) **on or before** the row date (payment date, else the day the e-mail arrived).
Amount is rounded to the currency's `sap.tcurx` decimals first (JPY 0, KWD 3). Factor = `ukurs x tfact / ffact` (INR, JPY, KRW
are per 100). USD needs no rate. A row with no rate (or no amount) is **flagged** (`usd_status`, `usd.unconverted` and
`usd.missing_rate_currencies` in the KPIs) and left out of the USD sums - never counted as 0.

## Actions per role (`app/permissions.py`)
By decision, from the Knowledge Base table; the AR Supervisor may act on every open row (no Escalate), other roles on rows
assigned to them, the AR Analyst on any open row. Closed rows offer nothing. The actions themselves are built in M09.

## Other changes
- `ar.work_item.region` (BSID XREF2, kept after the item is cleared) + indexes (migration `a7c3d1e9b002`); the matcher fills it.
- CORS: only the origins in `CORS_ORIGINS` (localhost now; the Static Web App origin is added in M08). No wildcard.
- New library: PyJWT 2.10.1.

## Checks
562 tests pass (19 new): login, lockout, audit, expiry, signed links, filters, KPI sums against hand-computed USD, rows without a
rate, role actions, change feed, CORS. Performance on 5,000 rows (history size): list, KPIs and audit each < 1 s (measured in the
tests; local database).

## Limits
- The login rate limit is per API process (fine for one replica).
- `region` for rows matched before this module was backfilled from the open item; rows with no BSID match have none.
- The USD rates in the sample data are synthetic.
