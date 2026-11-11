# Publish the HACS integration entirely in the browser

**No installation, publishing, or configuration scripts are required or included.** You do not need PowerShell, a terminal, Python, Node, Git CLI, or SSH on Windows or on Home Assistant. The integration itself is Python code, which Home Assistant loads normally after HACS installs it; that is not a user-run installer.

This ZIP contains the repository *contents*. It is not directly installable by HACS until you publish the files to a **public GitHub repository**. This repository has not been created or published for you.

## One-time GitHub publication (browser only)

1. Download and extract the source ZIP on Windows.
2. In the **GitHub website**, choose **New repository**. Use the name `water-treatment-monitor`, set it **Public**, and create it. Do not initialize it with another README or license; this ZIP already contains both. Publishing source publicly is required for this normal HACS custom-repository path; **never upload private history, screenshots, credentials, or your personal setup note**.
3. On the new repository page choose **Add file → Upload files** and drag the *contents* of the extracted folder (the root files and folders, not the ZIP or containing directory) into the browser. Ensure these paths exist in the repository: `hacs.json`, `custom_components/water_treatment_monitor/manifest.json`, `.github/workflows/validate.yml` and `README.md`. Commit using GitHub's webpage.
4. In GitHub's file browser open `custom_components/water_treatment_monitor/manifest.json` → **Edit** (pencil). Replace **both** occurrences of `REPLACE_WITH_OWNER` with your actual GitHub username or organization, leaving the `water-treatment-monitor` repository name unchanged. Commit the edit in the web page. Optionally set `codeowners` to your account, such as `["@your-account"]`, if you will maintain the integration. These are plain text edits on GitHub, **not script execution**.
5. Open **Actions → Validate integration**. Confirm the tests, HACS validation and hassfest have completed successfully. Fix any reported errors before releasing. A workflow appearing in the repo is not proof it has passed.
6. Use **Releases → Draft a new release** in GitHub's website. Create tag `v2.0.0rc5` from the validated commit, title it `Water Treatment Monitor v2.0.0 RC5`, mark **pre-release**, and publish. The manifest version is `2.0.0rc5`; the `v` prefix on a GitHub release tag is intentional.
7. Copy the GitHub repository address displayed in the browser, such as `https://github.com/YOUR_ACCOUNT/water-treatment-monitor`. Follow [QUICK_START.md](QUICK_START.md) to install it through HACS.

All validation runs **on GitHub Actions**, not on your computer. The `tests/` directory and `.github/workflows/validate.yml` are developer checks and are never installed into Home Assistant by HACS.

**If you choose another repository name:** edit the `documentation` and `issue_tracker` URLs to that name in GitHub's website as well.

## Updating later

1. Upload changed repository files through GitHub's web interface and commit them.
2. Confirm GitHub validation succeeds.
3. Publish a **new release** with an incremented `version` in `manifest.json` and matching tag. Do not change a published tag in place.
4. Take a verified **off-device backup** of `/config/water_treatment_monitor.sqlite3` before any upgrade that may migrate the database.
5. Use HACS's normal **Update/Download** action, then restart Home Assistant if prompted. No file manager or command line is required for updates.

## Scope and remaining manual UI setup

HACS manages only the integration code under `/config/custom_components/water_treatment_monitor/`. It does not publish the source repo, create a dashboard, register its card resource, test a user's sensor, back up the SQLite archive, or perform an existing-record migration. Those tasks use **Home Assistant's normal UI** and are documented in [QUICK_START.md](QUICK_START.md). Historical pump records live separately at `/config/water_treatment_monitor.sqlite3`. Replacing code does not itself erase the file, but future code could migrate it.

An external review of HACS/hassfest or a successful GitHub release is not evidence that this integration has been runtime-tested inside HA. This release is still a **developer release candidate**.
