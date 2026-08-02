# Phase 0 design

## Goal

Make source export and clean builds repeatable without changing runtime behavior.

## Change set

- Keep only safe examples in source control and deny secret, dump, key, archive, backup, and generated paths.
- Replace the broad source-dump helper with a tracked-file allowlist export.
- Make export fail when forbidden content is found and make a redacted secret scan mandatory before archive creation.
- Add a CI job that creates the source archive, extracts it in a clean folder, and builds both images from that folder.
- Fix the GitHub secret-scan command for the pinned scanner version.

## Compatibility

- Database: no change.
- API: no change.
- Frontend behavior: no change.
- Feature flags: none.
- Rollback: revert only the Phase 0 script, ignore, CI, and documentation changes.
- Manual work: install the pinned scan tool for local export; complete the incident checklist before release.
