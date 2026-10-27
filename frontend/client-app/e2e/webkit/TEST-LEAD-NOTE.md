# WebKit on macOS: accessibility and visual checks for first-visit pages

**For:** test lead · **Scope:** landing (`/`), sign in (`/login`), create account (`/register`) in the client app

## What we now have
- A Playwright project, `webkit-macos` (Desktop Safari), with six tests in `e2e/webkit/first-visit.spec.ts`. Each page gets one axe check (`@a11y`, WCAG 2.0/2.1 A and AA, no rules disabled or excluded, full axe JSON attached to the report) and one full-page screenshot comparison (`@visual`).
- Run it on a Mac with `npm run test:e2e:webkit` from `frontend/client-app`.
- **Isolation from Linux:** the project only exists when `process.platform === "darwin"`, and the `chromium` project ignores `webkit/**`. Baselines live only under `e2e/webkit/__screenshots__/webkit-macos-darwin/`, so Linux runs never load or compare them.

## What axe found, and how it was fixed
Playwright WebKit and real Safari 26.6.2 reported the same problems. All were fixed in the app.

| Page | Problem (axe rule) | Fix |
|---|---|---|
| Sign in | Subtitle contrast 1.41:1, introduced by the latest "Soften sign-in subtitle colour" commit (color-contrast) | `text-gray-500` |
| Sign in, Create account | Show/hide password buttons had no accessible name, so screen readers announced them as just "button" (button-name, critical) | `aria-label` that switches between "Show/Hide password" and "Show/Hide confirm password" |
| Landing | Contrast below 4.5:1 on the "Create Account" CTA (3.03:1), leadership titles (4.25:1), and Newsroom dates and footer (2.53:1) (color-contrast) | New `accent-700/800` shades and gray-500 text. Accent 400–600 are unchanged, so the rest of the app looks the same. |

After the fix, all three pages report 0 violations, both in Playwright WebKit and in Safari. The suite passed 6/6 on repeated runs.

## Evidence (in `e2e/webkit/evidence/`)
- axe output from both runs: `axe-before-*.json`, `axe-after-*.json`, plus the Safari panel text in `safari-axe-{before,after}-*.txt`.
- Safari screenshots before and after: `safari-before-*.png`, `safari-after-*.png`. The after set includes Web Inspector showing the toggle's name changing from "Show password" to "Hide password".
- Suite pass: `webkit-suite-pass.png`, `webkit-suite-after.log`. `axe-safari-overlay.js` re-runs the same axe check in Safari's console and outlines each violation.

## Things to know
- **This suite doesn't run in CI yet.** CI is Linux only, so the suite only runs when someone runs it on a Mac. The obvious next step is a `macos-latest` job that runs `npm run test:e2e:webkit`.
- **Baselines depend on the WebKit build.** After a Playwright upgrade or an intended UI change, regenerate them with `npm run test:e2e:webkit -- --update-snapshots` and review the PNG diff in the PR.
- **Restart Vite after any `tailwind.config.ts` change** before you capture baselines or run axe. A running dev server keeps serving the old CSS, and Playwright reuses it (`reuseExistingServer`). That makes axe pass without really checking the new styles. We hit this once, and the landing baseline was regenerated.
- **CI on this PR has two failures, neither caused by this change:**
  - `client-e2e` fails on the deliberately racy margins test (`renders a mocked SKU row`), which also fails on the base branch.
  - `parity` fails because the runner uses Python 3.14 and `psycopg[binary]==3.2.9` has no cp314 wheel.
  - Separately, `@axe-core/playwright` 4.14 declares Node >=22.12. CI's Node 20 only logs an engine warning.
- **axe isn't a full audit.** It catches roughly a third to half of WCAG issues. Keyboard order and VoiceOver announcements still need a manual pass.
