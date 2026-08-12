# Release Guide

## Source Release

1. Review `git status` and confirm that no local configuration, logs, databases, downloaded files, or reference-only material is tracked.
2. Run the checks from `CONTRIBUTING.md` and `scripts/check_public_safety.py`.
3. Review dependency and third-party notices, especially bundled fonts and platform packaging.
4. Refresh `requirements.lock` with `uv pip compile --universal --python-version 3.10 --generate-hashes requirements.txt -o requirements.lock` after reviewing dependency changes. The lock must cover the documented minimum Python version.
5. Update `CHANGELOG.md`, `SoftwareOrganizer.spec`, and the API version together.
6. Create an annotated version tag, for example `v1.5.0`.
7. Verify the tag build and attach checksums to a GitHub Release when binary publication is approved.
8. Confirm that the packaged bundle contains `LICENSE` and `THIRD_PARTY_NOTICES.md`.

## macOS Application

`./scripts/build_standalone.sh` creates `dist/FileOrganizer.app` from the reviewed `requirements.lock` in a disposable virtual environment. Set `PYTHON_BIN` when a specific supported Python interpreter is required. Current CI artifacts are Apple Silicon (`arm64`) and ad-hoc signed. A public macOS download should use Developer ID signing and notarization, provide a checksum, and be distributed as a documented release asset rather than committed to the repository.

## Windows Application

Windows uses `SoftwareOrganizer.windows.spec` and produces `dist/FileOrganizer/FileOrganizer.exe`. The GitHub Windows job is manual-only and remains skipped for version tags; run it only with the explicit `build_windows` input after validation on a real Windows target. Sign the executable before presenting it as a trusted public download.

Windows support remains experimental until the packaged application completes real-device validation.

## Release Gate

Do not publish a binary when any of these are unresolved:

- a provider key, personal path, real log, or local database is present;
- a bundled asset lacks an applicable license notice;
- a platform build has not been tested on its target platform;
- the app is unsigned while the release page implies trusted installation;
- cleanup, transfer, or path-boundary tests fail.
