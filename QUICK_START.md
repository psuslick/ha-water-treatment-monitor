# Quick start — Water Treatment Monitor v2.0.0 RC5

**Hard rule: no install scripts.** You do not need a terminal, PowerShell, Git, Python, Node, YAML packages, or any helper script. GitHub publication and Home Assistant setup use only their normal graphical interfaces.

### Part A — Put the source on GitHub (one time)

1. Extract the repository ZIP on Windows, then follow the [browser-only publishing guide](PUBLISHING.md). Upload the extracted **files and folders**, not the ZIP itself.
2. In GitHub's web editor, replace the two `REPLACE_WITH_OWNER` values in `custom_components/water_treatment_monitor/manifest.json` with your actual GitHub account. Do not put personal HA data in the public repository.
3. Check GitHub **Actions** for completed green validation results. Publish GitHub pre-release tag `v2.0.0rc5` through **Releases**. Do not install if HACS/hassfest validation fails.

### Part B — Install through HACS / Marketplace (no scripts)

1. In Home Assistant's **HACS** interface, open **Custom repositories** (or your version's **Marketplace → Add from link**) and paste your *published* GitHub repository URL. Choose **Integration** if prompted.
2. Open **Water Treatment Monitor**, select **Download** and choose release `v2.0.0rc5` (turn on pre-release visibility if the selector requires it).
3. Restart Home Assistant through its UI, then **Settings → Devices & services → Add integration → Water Treatment Monitor**.
4. Select the existing pump binary sensor. Enter the **first reliably confirmed ON timestamp with its timezone offset**. Your personal values are supplied in the separate **private setup note**; do not publish that note on GitHub. This cutoff prevents the earlier magnet/contact tests from being imported.
5. Verify the integration reports successful import/health before using any graph as evidence of operational behavior.
6. **Settings → Dashboards → Resources:** add JavaScript module URL `/water_treatment_monitor/water-treatment-card.js` once. Then create a dashboard in UI/storage mode and paste the contents of [`water_treatment_dashboard.yaml`](water_treatment_dashboard.yaml) into its **Raw configuration editor**. There is no separate JS file transfer.
7. Configure the softener and neutralizer schedules in the card; preserve uncertainty when recurrence is demand-based or unknown. Enter measured pH and independently observed manual events when available.
8. Complete the [live acceptance checklist](VALIDATION.md), including a sample pump cycle, archive coverage, backwash window comparisons, SQLite snapshot and **off-device** backup test.

### What you do **not** do

- No command-line setup, repository-personalization tool, `pip` install, or custom installer.
- No manual copying of integration Python or JavaScript files into Home Assistant when using HACS.
- No legacy YAML package/Local Calendar monitoring automation running alongside this integration.
- No assumption that a scheduled backwash proves the controller actually regenerated.

**Status:** Repository source created locally; not published on GitHub, not installed in HA, not runtime-verified.
