# RC6 tradeoffs and compatibility

- **GUI-only:** HACS downloads the code after it is published to GitHub; configure existing pH button/value helpers through the integration's Options screen. No scripts, YAML, HA API writes, or manual Python installation are required.
- **Optional legacy pH bridge:** The integration's own pH form is independent. The existing Home Assistant pH button does nothing unless both helper entities are explicitly linked in the Options screen. Once linked, each button press creates a *new* treated-water sample using the number helper's value at that moment. The initial 4.0 value may be a placeholder. This is a deliberate user-triggered record, not automatic measurement.
- **Historical sample range:** The main analysis date range filters the pH history graph/table, not writes to the archive. RC6 explicitly confirms saves outside the selected range.
- **Safety:** The integration is observational and does not operate any treatment equipment. SQLite database remains separate from code. No schema changes or automatic delete/migration in RC6.
- **Threading:** RC6 marks dispatcher refresh listeners as Home Assistant callbacks; the HA event-loop scheduling path must still be verified after live update.
- **Release:** The GitHub repository must be updated and the prerelease `v2.0.0rc6` must exist before HACS offers the new version. Uploading this ZIP in chat does not publish it or alter HA.
