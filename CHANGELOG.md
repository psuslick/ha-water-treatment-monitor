# Change log

## 2.0.0rc5 — browser-only HACS publishing and installation

- Removed the `tools/` directory, including `configure_repository.py` and `check_release.py`.
- Removed every local command-line/personalization/test step from installation and publishing guidance.
- Repository owner metadata is now filled using **GitHub's normal file editor** (two occurrences), not an installer script.
- Retained automatic GitHub Actions regression, HACS and hassfest validation; these are **hosted CI checks**, not user-run setup steps.
- Updated manifest version/tag and all guides for `v2.0.0rc5`.
- **No changes to pump capture, SQLite archive, schedule analysis, data quality logic, frontend behavior, or setup data schema.**

---

# Changelog

## v2.0.0 RC4 — HACS repository candidate

- Retained the RC3 SQLite archive schema, event semantics, sensor unique IDs, bundled frontend, graph calculations and snapshot/export interfaces.
- Added HACS-compatible repository structure and author-provided `hacs.json` metadata, GitHub Actions for HACS validation, hassfest and source tests.
- Added a `brand/icon.png`, MIT license, repository configuration helper, release checker, and publish/upgrade documentation.
- **Behavioral configuration change:** `pump_entity` is no longer hardcoded. Setup selects the source sensor; optional `import_start` is an immutable, timezone-aware first-reliable-observation boundary. This prevents a public HACS project from carrying one home's hardcoded commissioning timestamp or incorrectly excluding someone else's pump history.
- Kept historical archive outside HACS-managed folders, preventing normal code-file updates from replacing it. Existing RC3 archive import cutoff remains intact if the same source is reconnected and `import_start` is left blank; a contradictory cutoff is refused instead of rewriting historical records.
- Updated all English config-flow strings and translations for the new onboarding field.
- Used a stable frontend resource URL so routine HACS updates don't require manually changing a version query parameter; a browser reload may still be necessary.
- Replaced the household-specific test replay in the public repository with synthetic cutoff and deduplication tests. The behavior remains tested, but historical household records are not published with the code.

## v2.0.0 RC3 — predecessor, superseded

- Introduced the initial import cutoff for known commissioning data and guarded against silent destructive migrations.

## v2.0.0 RC2 — predecessor, superseded

- Added audited data-quality exclusions, exact time-overlap and midnight boundaries for charts, and frontend unsaved-edit protections.

## v2.0.0 RC1 — predecessor, rejected

- First version of dedicated SQLite archive; not approved for installation because of incorrect commissioning and graph behavior.
