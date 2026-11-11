# Water Treatment Monitor v2.0.0 RC6 — HACS GUI update

1. Back up Home Assistant **including** `/config/water_treatment_monitor.sqlite3` (your historical data); preserve an off-device backup.
2. On GitHub, upload **the extracted repository ZIP contents** to the root of `psuslick/ha-water-treatment-monitor` using the website; commit them. Do not upload the ZIP as one file. The `.github` folder must be included. No scripts.
3. In the GitHub website **Actions** tab, ensure all repository checks pass, then create a prerelease tagged `v2.0.0rc6`.
4. In Home Assistant's HACS, choose the new `v2.0.0rc6` release to download/update Water Treatment Monitor. Restart Home Assistant via Settings.
5. Refresh the Water Treatment dashboard with a hard reload (`Ctrl+Shift+R`) so the updated JavaScript is loaded.
6. The dashboard's **Manual runs & pH → Record pH** now reports either the exact save result or an error on its own form. The selected analysis range filters the graph/history only, never whether the archive stores your sample.
7. **If you use an older separate HA Record pH button helper:** Go to **Settings → Devices & Services → Water Treatment Monitor → Configure**. Select BOTH:
   - Record pH button: `input_button.record_ph_reading_entry`
   - pH numeric helper: `input_number.final_treated_ph_entry`
   Save the options. The integration reloads. Enter the actual measured pH in your helper BEFORE pressing the button. Existing value `4.0` may just be its default, not a real test.
8. Verify a pH sample appears in **Manual runs & pH → pH sample history** using an analysis range containing its timestamp. Confirm no fresh Water Treatment Monitor thread-safety errors in HA logs.

**Status:** RC6 local candidate, pending GitHub publication, HACS update, and live acceptance testing. Neither release nor this archive is automatically uploaded to GitHub/HA.
