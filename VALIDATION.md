# Water Treatment Monitor RC5 — validation checklist

## GitHub/HACS repository (browser only; NOT YET VERIFIED)

- [ ] The repo is **public** and has `hacs.json`, `README.md`, `.github/workflows/validate.yml`, and `custom_components/water_treatment_monitor/manifest.json` at their correct paths.
- [ ] The prefilled manifest links open `psuslick/ha-water-treatment-monitor` and its issue tracker, and the code owner is `@psuslick`.
- [ ] **Actions → Validate integration** is green for `local-tests`, `hacs` and `hassfest` on the published commit; these tests run remotely and require no local commands.
- [ ] A GitHub prerelease `v2.0.0rc5` exists, and HACS recognizes it as an Integration custom repository.
- [ ] Home Assistant restarts and the config flow loads; no install scripts or terminal steps were necessary.

## Live HA acceptance (NOT YET PERFORMED)

- [ ] The initial pump source is verified and the historical import floor is precisely the first reliable ON timestamp. Commissioning edges are not imported; first valid ON/OFF interval and later runs are.
- [ ] No data was silently lost, duplicated, or re-imported across a restart/backfill. Gaps remain visible.
- [ ] The baseline excludes commissioning artifacts but retains genuine abnormal/long later runs.
- [ ] Hour/day/week/month/year numbers are calculated from valid archive records with honest coverage flags.
- [ ] Starts-inside a backwash, runs-overlapping a window, and exact pump-on seconds are distinct and reproducible, including midnight/DST boundaries.
- [ ] The expected treatment windows derive from the historical effective schedule; uncertain recurrence never creates fictitious windows.
- [ ] pH, schedules and manual backwash records can be added, corrected, and inspected without losing unsaved edits.
- [ ] SQLite snapshots and CSV export work. Confirm the actual Home Assistant backup includes the SQLite archive and verify a separate **off-device** restore in an isolated setting.
- [ ] A genuine HA restart/unavailability episode does not create a false complete pump run. Never interrupt pump equipment for a test.
- [ ] CPU, RAM, database growth and dashboard responsiveness remain satisfactory after real use.

**No live installation, successful HACS validation, or off-device backup recovery is claimed by the source ZIP alone.**
