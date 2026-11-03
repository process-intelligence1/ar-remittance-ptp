# Dependabot triage - 3 Nov 2026 (after M09)

81 open alert rows on `main` before this change. Source: GitHub Dependabot API. Alerts are re-scanned by GitHub after the push, so the "after" column is expected, not yet confirmed.

## Counts
| Group | What | Before (rows) | Critical / high now |
|---|---|---|---|
| (a) shipped at runtime | PyJWT in the API and worker images (16 advisories; GitHub lists each once per requirements file = 48 rows incl. the laptop-only `requirements-dev.txt`), `react-router-dom` / `@remix-run/router` in the browser bundle, `minimatch` / `uuid` inside the prebuilt ExcelJS bundle | 48 + 7 = 55 | 0 after the upgrades |
| (b) dev / build only | `vite`, `vitest`, `tinypool`, `@vitest/mocker`, `esbuild` (laptop, tests, build; not in any image or bundle) | 25 (4 critical, 1 high, 17 medium, 3 low) | list for M13 |

(a) before: 1 critical + 6 high distinct advisories (PyJWT 1 critical + 5 high, `@remix-run/router` 1 high).

## Fixed now (group a, critical and high)
- PyJWT 2.10.1 -> 2.15.1 in `requirements.txt` (worker image) and `requirements-api.txt` (API image). Clears all 16 PyJWT advisories (the newest fix is in 2.15.0).
- `react-router-dom` 6.28.0 -> 6.30.6 (pulls `@remix-run/router` 1.23.4 and `react-router` 6.30.6). Clears the high alert and the two `react-router` 6.30.x alerts.
- Tests after the upgrades: 588 back-end, 66 front-end, build OK.

## Left in group (a) - medium only, not fixable by a patch upgrade
- `react-router` advisory with fix only in 7.18.0 (React Router 7 is a breaking major upgrade; the route code would need migrating).
- `minimatch` 11.0.1 and `uuid` 11.1.1: both are copies inside `exceljs.min.js` (prebuilt by ExcelJS 4.4.0, the latest ExcelJS; `npm audit` suggests a downgrade to 3.4.0, which is not an option). Not reachable from our code: the file is built in the browser from the user's own confirmed cases; no untrusted input reaches those functions. Revisit if ExcelJS publishes a new release.

## Group (b) for M13 (dev / build only)
| Package | Alerts | Worst | Fix path |
|---|---|---|---|
| vitest | 3 | critical | upgrade 2.1.8 -> latest 4.x (test runner, laptop only) |
| tinypool | 2 | critical | comes with vitest; fixed by the vitest upgrade |
| vite | 17 | high | upgrade 5.4.11 -> latest 6.4.x / 7.x together with `@vitejs/plugin-react` (dev server and build tool; not shipped) |
| @vitest/mocker | 2 | medium | with vitest |
| esbuild | 1 | medium | with vite |
Notes: these affect only the laptop dev server / test runner and the GitHub build; the built site and the images do not contain them. Upgrading vite and vitest together is one change; re-run all tests and the build, and check `VITE_BASE` / proxy config still work.
