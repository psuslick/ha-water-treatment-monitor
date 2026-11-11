# Publish the HACS integration entirely in the browser

**No installation, publishing, or configuration scripts are required or included.** You do not need PowerShell, a terminal, Python, Node, Git CLI, or SSH on Windows or on Home Assistant. The integration itself is Python code, which Home Assistant loads normally after HACS installs it; that is not a user-run installer.

This ZIP contains the repository *contents*. It is not directly installable by HACS until you publish the files to a **public GitHub repository**. Your repository address is `https://github.com/psuslick/ha-water-treatment-monitor`. Its contents and release status must still be confirmed in GitHub.

## One-time GitHub publication (browser only)

1. Download and extract the source ZIP on Windows.
2. Open your existing repository: **https://github.com/psuslick/ha-water-treatment-monitor**. Confirm it is **Public**. The ZIP already contains its README and license. **Never upload private history, screenshots, credentials, or your personal setup note.**
3. On the repository page choose **Add file → Upload files** and drag the *contents* of the extracted folder (the root files and folders, not the ZIP or containing directory) into the browser. Ensure these paths exist in the repository: `hacs.json`, `custom_components/water_treatment_monitor/manifest.json`, `.github/workflows/validate.yml` and `README.md`. Commit using GitHub's webpage.
4. Verify `custom_components/water_treatment_monitor/manifest.json` has links to **https://github.com/psuslick/ha-water-treatment-monitor**, the issues page, and code owner `@psuslick`. These fields are already filled in this ZIP; **no manual metadata edits or scripts** are needed.
5. Open **Actions → Validate integration**. Confirm the tests, HACS validation and hassfest have completed successfully. Fix any reported errors before releasing. A workflow appearing in the repo is not proof it has passed.
6. Use **Releases → Draft a new release** in GitHub's website. Create tag `v2.0.0rc5` from the validated commit, title it `Water Treatment Monitor v2.0.0 RC5`, mark **pre-release**, and publish. The manifest version is `2.0.0rc5`; the `v` prefix on a GitHub release tag is intentional.
7. Open [QUICK_START.md](QUICK_START.md) to install from **https://github.com/psuslick/ha-water-treatment-monitor** through HACS.

All validation runs **on GitHub Actions**, not on your computer. The `tests/` directory and `.github/workflows/validate.yml` are developer checks and are never installed into Home Assistant by HACS.

**Note:** The repository URL and public code-owner name are already configured; if this repository is renamed later, update the manifest URLs.

## Updating later

1. Upload changed repository files through GitHub's web interface and commit them.
2. Confirm GitHub validation succeeds.
3. Publish a **new release** with an incremented `version` in `manifest.json` and matching tag. Do not change a published tag in place.
4. Take a verified **off-device backup** of `/config/water_treatment_monitor.sqlite3` before any upgrade that may migrate the database.
5. Use HACS's normal **Update/Download** action, then restart Home Assistant if prompted. No file manager or command line is required for updates.

## Scope and remaining manual UI setup

HACS manages only the integration code under `/config/custom_components/water_treatment_monitor/`. It does not publish the source repo, create a dashboard, register its card resource, test a user's sensor, back up the SQLite archive, or perform an existing-record migration. Those tasks use **Home Assistant's normal UI** and are documented in [QUICK_START.md](QUICK_START.md). Historical pump records live separately at `/config/water_treatment_monitor.sqlite3`. Replacing code does not itself erase the file, but future code could migrate it.

An external review of HACS/hassfest or a successful GitHub release is not evidence that this integration has been runtime-tested inside HA. This release is still a **developer release candidate**.
