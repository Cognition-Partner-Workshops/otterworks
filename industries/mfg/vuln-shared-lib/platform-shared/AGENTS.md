# AGENTS.md: platform-shared

Owned by `platform-team`. This library is consumed by `../dev-api` (Dealer, Warranty, Payments, Identity) and the BFF in `../dealer-portal`.

- Run `make test` before and after a change. It must pass on the first command.
- The public surface is pinned in `tests/Platform.Shared.Tests/PublicApi.approved.txt`. Never change or remove a public signature in place: add the new overload, keep the old one with `[Obsolete]` and a message that names the replacement, and bump `<Version>`.
- After changing the library, run `make pack` (or `make vsl-pack` from the repository root) and run both consumers' tests against the local feed before opening a PR. The commands are in `.agents/skills/shared-library-consumers/SKILL.md`.
- Identity access tokens are signed by `TokenSigner`. The Android app's sign-in tests pin the token the Identity API returns, so a signing change also needs `../android-app` tests.
- No new package dependencies without a note in the PR description.
- Fixture keys and hosts in this directory are synthetic; never add a real credential or a real customer name.
