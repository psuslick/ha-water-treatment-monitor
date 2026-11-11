# RC5: no installation scripts — changes and tradeoffs

## Removed

- Removed **both** repository helper scripts (`tools/configure_repository.py` and `tools/check_release.py`) and the `tools/` folder.
- Removed all user-facing instructions to run a terminal, PowerShell, Git CLI, Python, or Node for installation or publication.
- Removed the associated custom release-check step from GitHub Actions.

## Retained

- **HACS** installs and updates the integration code directly from a published public GitHub repository. No manually copied Python/JavaScript files.
- GitHub Actions still performs Python regression tests and frontend checks **automatically in GitHub's hosted runner**, plus the HACS and hassfest validators. These checks are not user-run installation scripts.
- The native HA **config flow** selects the sensor and import start; the card and dashboard are configured using the normal HA interface.
- The SQLite archive remains outside `custom_components/` so ordinary HACS code updates do not overwrite it. Historical correctness, archive schema, schedule engine, pump observations and data-quality rules are unchanged.

## Tradeoffs

- A one-time **public GitHub browser upload** is still necessary because this repository has not yet been published. HACS cannot download the provided ZIP directly and cannot invent a GitHub repository address.
- The repository URLs and public code owner are already set to `psuslick/ha-water-treatment-monitor`. **No setup scripts or metadata edits** are needed. A repository rename would require updating the manifest URLs.
- Because script-based local checks were removed from the publish procedure, checking **GitHub Actions** is a release gate rather than an optional convenience. Green CI still does not prove live HA runtime behavior.
- Dashboard YAML is a one-time UI import and is not updated automatically by HACS. Frontend JavaScript is bundled and upgrades with the integration.
- Code and setup still require trust in a custom integration. HACS does **not** back up the archive or guarantee years of retention without verified off-device backups.

**Result:** No scripts for you to execute to install, publish, or update; no runtime monitoring functionality intentionally changed from RC4.
