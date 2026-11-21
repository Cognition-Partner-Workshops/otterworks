# Parity: Tosca `TestCases/Settings` → Playwright

Sources: `tests/legacy-suites/tosca/ExecutionLists/ClientRegression.xml`,
`ExecutionLogs/client-regression-2025-02.xml`, `ExecutionLogs/Screenshots/settings.png`,
`Modules/Settings.xml`, and `TestCaseDesign/Settings.csv`.
Run: `npx playwright test --project tosca-migrated` (local Vite, Chromium, mocked API).

| TestCase ID | Playwright test | Tosca result (last log) | Playwright result | Verdict | Decision and reason |
| --- | --- | --- | --- | --- | --- |
| TC-SET-001 | `settings.spec.ts` › `TC-SET-001 View profile settings` (`@TC-SET-001`) | Passed | Passed | Match | Asserts Settings heading and the name/email input values from the unchanged Profile CSV row, matching settings.png. AuthController GET profile returns camelCase UserDTO, not snake_case. |
| TC-SET-002 | `settings.spec.ts` › `TC-SET-002 Update email notification preference` (`@TC-SET-002`) | Passed | Passed | Match (Playwright checks more) | settings.png shows email enabled after the logged single click; the stored precondition is therefore disabled (not the new-user service default true). Playwright checks false before the click and true in API state afterward. There is no literal Enabled text or accessible toggle state in the app: the unnamed button is reached by Tab from Email, skipping disabled Save. This accessibility gap prevents a role/name or checked assertion; the persisted service boolean proves Enabled instead. |
| TC-SET-003 | `settings.spec.ts` › `TC-SET-003 Save profile details` (`@TC-SET-003`) | Passed | Failed (expected via `test.fail()`) | App regression: profile update uses PATCH instead of PUT | SettingsContent submits through authApi.updateProfile using PATCH; AuthController only maps PUT /profile. The faithful mock returns 405 without changing the user. After reload Full name remains Alex Morgan instead of Casey Taylor. Tosca only reread the edited input and its screenshot still shows Alex Morgan, so its pass did not prove persistence. Playwright retains the reload assertion and expected failure, with trace/screenshot artifacts. |

Defect: `PATCH /api/v1/auth/profile` sends `{displayName, email}` to a PUT-only endpoint; the 405 response leaves the saved displayName unchanged (email is not an UpdateProfileRequest field).

Contract evidence: `services/auth-service/src/main/java/com/otterworks/auth/`:
`controller/AuthController.java`, `controller/SettingsController.java`,
`service/UserService.java`, `service/UserSettingsService.java`, `dto/UserDTO.java`,
`dto/UpdateProfileRequest.java`, `dto/UserSettingsDTO.java`, and `entity/UserSettings.java`.
Mocks keep per-test state, honor non-null update fields, reject unsupported methods,
and preserve camelCase responses. No application code was changed.
The project retains its trace/screenshot-on-failure settings, but Playwright does not
retain those artifacts for an expected failure; this run provides error-context.md
in the HTML report instead. The report summary counts the expected failure as passed.

History check: `git log -S` against `frontend/client-app/src` found no occurrence
history for Alex Morgan, Casey Taylor, or Enabled; Settings appears in a324a50d5.
The names are fixture inputs, not hard-coded app copy; no sheet correction is needed.
Enabled is represented by the persisted boolean, as shown by the screenshot and toggle implementation.
The screenshot is shared by the three logged cases, so the disabled starting state is
an inference from TC-SET-002's click plus its enabled end state, not an observed pre-click screenshot.
