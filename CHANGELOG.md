# Water Treatment Monitor v2.0.0 RC6 — live bugfix update

- Fix unsafe dispatcher callback scheduling observed in Home Assistant 2026.11 logs (thread-safety violation).
- Fix stale schedule create form and duplicate click retries; refresh revision table after successful writes.
- Fix dashboard pH form errors appearing under the wrong form; display precise validation errors and persistent save confirmation.
- When an entered pH date is outside the selected chart range, clearly state that the saved record is archived but filtered out of that graph.
- Add **optional** GUI integration options for existing `input_button` + `input_number` pH helpers. When selected, each actual button press records the contemporaneous numeric value as a treated-water sample; startup or unknown states are ignored. Neither helper is hard-coded into public source.
- No DB schema changes, archive purge, equipment control, user-executed scripts, or changes to pump import cutoff.
- Use HACS GUI to update and configure integration; restart Home Assistant after updating source.

**Important:** If the user presses the legacy helper button with the default value 4.0, a 4.0 sample will be recorded. Verify the number first. The dashboard's built-in pH form does not require helper configuration.
