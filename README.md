# Water Treatment Monitor

**v2.0.0 RC5 — HACS repository candidate — observational only, not production-verified.**

A local Home Assistant integration for tracking individual well-pump cycles, recording versions of softener and neutralizer regeneration schedules, comparing *expected* backwash windows with observed pump behavior, and logging pH samples.

## Key properties

- Monitors one user-selected binary sensor (`on` means energized). **Never starts or controls a pump or a treatment valve.**
- Archives individual ON/OFF observations and verified completed cycles in `/config/water_treatment_monitor.sqlite3` using indexed SQLite transactions. Preserves the original observation records for years unless manually removed or the storage fails.
- On initial setup, optionally sets the **earliest reliable observation time** as an ISO 8601 timestamp with a timezone offset. Earlier commissioning events are not imported into the dedicated archive. This cutoff is user-defined rather than built into publicly distributed source. Never silently deletes an existing archive to change a cutoff.
- Imports available Recorder history on setup and on future restarts; existing events are deduplicated. **History already purged by Recorder cannot be reconstructed.**
- Keeps editable, effective-dated water-softener and neutralizer schedules, manual regeneration events, and timestamped pH measurements, with a correction audit log.
- Graphs expected backwash times versus pump relay activity, pump starts *inside* a window versus runs *overlapping* it, active seconds per treatment phase, daily split runtimes, and per-run duration outliers. Expected does not mean confirmed; pressure-tank storage may allow regeneration without a pump start.
- Shows day/week/month/year statistics from the archive and flags incomplete observation coverage.
- Supports an on-demand SQLite snapshot and CSV ZIP export; creates periodic **same-device** local snapshots. Off-device backups and recovery tests remain the operator's responsibility.

## HACS installation (no scripts)

HACS only accepts a properly structured **public GitHub repository** for a custom repository. This deliverable is a **repository template**, not an already published repository. It includes two `REPLACE_WITH_OWNER` links to update in **GitHub’s web editor**, not with scripts; see [PUBLISHING.md](PUBLISHING.md).

1. In HACS, open the menu → **Custom repositories**. Add the real GitHub repository URL and choose **Integration**. Download the selected version. A prerelease may require enabling prerelease downloads. [HACS documentation](https://hacs.dev/docs/faq/custom_repositories/).
2. Restart Home Assistant. Open **Settings → Devices & services → Add integration → Water Treatment Monitor**.
3. Select the pump **binary sensor**. If some of the sensor's historical states were commissioning tests, enter the **earliest reliable observation timestamp**, e.g. `2026-01-01T12:00:00-05:00`. Leave it blank **only when all recoverable history can be treated as valid**. Timestamp must include the timezone offset. This is an immutable archive boundary; changing it later requires backed-up migration.
4. Confirm the integration starts and the initial Recorder backfill status finishes before trusting baseline statistics.
5. Once, under **Settings → Dashboards → Resources**, register the JavaScript module `/water_treatment_monitor/water-treatment-card.js`. There is no separate frontend file to install, and future code updates use the same URL. If a stale card appears after an update, refresh the browser cache.
6. Once, create a **Water Treatment** dashboard in UI storage mode and paste [`water_treatment_dashboard.yaml`](water_treatment_dashboard.yaml) into its raw configuration editor. HACS **does not automatically create or update the Lovelace dashboard**.
7. Save actual controller schedules in the card (or mark `demand` / `unknown` if future dates cannot be predicted). Record manual cycles only where you have independent evidence. Enter pH results from measured samples.
8. Complete [`VALIDATION.md`](VALIDATION.md) before declaring the integration operational.

**Do not enable old Water Treatment YAML monitoring automations simultaneously.** Older Local Calendar records are not automatically migrated into the SQLite archive. This integration does not delete or modify them.

## HACS versus manual installation

HACS installs and updates only the files under `/config/custom_components/water_treatment_monitor/`. Because the frontend code is bundled there, it updates with Python code. The dashboard YAML is a **one-time manual import** and still needs intentional manual layout updates. The SQLite archive and snapshots live elsewhere in `/config`, so normal HACS code updates do not replace them. A future integration version **could migrate the database schema**, so take a verified off-device backup before updating. HACS itself is not a data backup system.

On a manual installation, copy **only** `custom_components/water_treatment_monitor/` to the matching directory in your HA `/config/`, restart and complete steps 2 onward. Do not copy repository tests, workflows or the README into HA.

## Historical and correctness limits

- Sensor relay continuity is an assumption, not independent verification that a motor ran. Availability gaps and partial ON intervals should not be treated as complete pump cycles.
- Archives are never automatically purged, but without an off-device copy they are vulnerable to disk loss or filesystem corruption.
- An expected backwash with zero pump starts is a **review candidate**, not proof the controller failed.
- Demand-based regeneration and unknown recurrence do not generate fictitious scheduled windows.
- Averages over incomplete periods are labeled as partial; they are not historical estimates of data not observed.
- Graph timestamps use browser-local time; recurrence and daily aggregation use the Home Assistant timezone. When traveling, check timestamps carefully.
- Updates are designed to preserve previously archived observations. A configuration-entry change to a different source is refused rather than silently combining data.

## Project layout

```text
custom_components/water_treatment_monitor/
  __init__.py config_flow.py const.py db.py analysis.py sensor.py websocket.py
  manifest.json strings.json translations/en.json
  frontend/water-treatment-card.js
  brand/icon.png
hacs.json
water_treatment_dashboard.yaml
.github/workflows/validate.yml
```

All publishing and installation steps are graphical; **you do not run setup scripts or terminal commands**. The `tests/` directory is for GitHub-hosted automated validation only. This is a pre-release developer build. Standalone tests, compilation and packaging checks are useful but do **not** prove Home Assistant runtime compatibility or safe years-long retention. No change to any existing HA installation is implied by this repository.
