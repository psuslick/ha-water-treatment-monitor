# Water Treatment Monitor RC6 — validation checklist

## GitHub/HACS repository (browser only; NOT YET VERIFIED)

- [ ] The repo is **public** and has `hacs.json`, `README.md`, `.github/workflows/validate.yml`, and `custom_components/water_treatment_monitor/manifest.json` at their correct paths.
- [ ] The prefilled manifest links open `psuslick/ha-water-treatment-monitor` and its issue tracker, and the code owner is `@psuslick`.
- [ ] **Actions → Validate integration** is green for `local-tests`, `hacs` and `hassfest` on the published commit; these tests run remotely and require no local commands.
- [ ] A GitHub prerelease `v2.0.0rc6` exists, and HACS recognizes it as an Integration custom repository.
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

## RC6 targeted acceptance (still required on the live instance)

- [ ] Confirm **Settings → Devices & Services → Water Treatment Monitor → Configure** offers optional `input_button` and `input_number` selectors; save both and confirm the integration reloads without disturbing its SQLite archive.
- [ ] Set a deliberate numeric helper reading (verify its current 4.0 is not just a default), press the selected helper once, then see exactly one corresponding **treated** sample in Manual runs & pH, with timestamp and audit entry.
- [ ] Submit a sample from the dashboard pH form. Confirm an explicit saved confirmation and a history row in an analysis range covering its timestamp.
- [ ] Submit an invalid pH entry, if the browser permits, and confirm errors are displayed under **Record pH** rather than **Manual backwash**.
- [ ] Recommit the same softener effective timestamp and confirm it is rejected cleanly with a helpful message, not a raw UNIQUE constraint. Existing revision remains in the history list.
- [ ] Confirm no **new** thread-safety warning from the integration in HA system logs after updating/restarting; older accumulated warnings do not prove a new failure.
- [ ] Confirm the original pump archive, schedule revisions and pH samples persist; validate off-device backup coverage.
