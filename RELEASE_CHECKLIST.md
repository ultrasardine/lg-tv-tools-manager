# Release Checklist

Release: `0.1.3`

## Before publishing

- Confirm the codebase is frozen at `0.1.3`.
- Run the smoke test:
  - `bash scripts/smoke_test.sh`
- Build the package:
  - `bash scripts/build_deb.sh`
- Verify the artifact exists:
  - `.build/lg-tv-tools_0.1.3_all.deb`
- If publishing a signed release, sign the package:
  - `bash scripts/sign_release.sh`
- Verify the signature file was created:
  - `.build/lg-tv-tools_0.1.3_all.deb.asc`
- Use the release key:
  - `88228B125455C0B7644DB1A9320D6B571195D41C`

## Metadata to keep stable

- Author: `Dantes de la Calle Frexes`
- User: `Reyam`
- Email: `rey.amado8509@gmail.com`
- Version: `0.1.3`

## Publish notes

- Use the same version in the tag, changelog, and package name.
- Do not change the release notes after signing.
- If the TV discovery or UPnP behavior changes, cut a new version instead of mutating `0.1.3`.
