# Contributing and releasing

## Development

Keep changes backward compatible unless a breaking change is intentional. Do not rename the `ford_connect` domain or change existing config-entry, OAuth, entity unique-ID, or API behavior as part of packaging work.

Before opening a pull request, run:

```bash
ruff check .
pytest -q
python -m compileall -q custom_components
```

## Versioning

The release version has one source of truth: `custom_components/ford_connect/manifest.json`. It uses Semantic Versioning (`MAJOR.MINOR.PATCH`):

- PATCH (`0.2.0` → `0.2.1`) for backward-compatible bug fixes.
- MINOR (`0.2.1` → `0.3.0`) for backward-compatible functionality.
- MAJOR (`0.9.0` → `1.0.0`) for breaking changes.

Versions represent releases, not commits. Keep the current release line at `0.2.x` until a backwards-compatible feature warrants `0.3.0`.

## Release process

1. Develop and merge the intended changes to `main`.
2. Run the validation commands above and choose the SemVer increment.
3. Update only `custom_components/ford_connect/manifest.json` with the release version, for example `"version": "0.2.1"`.
4. Update `CHANGELOG.md`, commit the version bump, and merge or push it to `main`.
5. Create and push a matching annotated or lightweight tag:

   ```bash
   git tag v0.2.1
   git push origin v0.2.1
   ```

6. The release workflow verifies that `v0.2.1` exactly matches `manifest.json`, runs the test and validation suite, then creates the GitHub Release with generated notes.
7. Confirm the release on GitHub. HACS uses GitHub Releases as the stable update channel and will detect the new version for installed users.

Never push a tag before the matching manifest version is present on the tagged commit. The release workflow intentionally fails on a mismatch and never creates a release when validation fails.