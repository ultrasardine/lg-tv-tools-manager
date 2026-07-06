# LG TV Tools 0.1.3

LG TV Tools 0.1.3 focuses on stability, packaging, and clearer diagnostics.

## Highlights

- More flexible LG TV discovery on SSDP/DLNA networks
- Better UPnP error reporting for media playback
- Compact UI with clearer status panels
- Added smoke testing for release validation
- Added local Debian packaging and optional GPG signing support

## Notes

- Direct media playback still depends on the LG model and network reachability.
- If the TV cannot reach the host URL, UPnP playback will fail even when discovery succeeds.

## Installation

- User-level integration:
  - `bash scripts/install.sh`
- Local package build:
  - `bash scripts/build_deb.sh`
- Smoke test:
  - `bash scripts/smoke_test.sh`

## Signature

- Signed releases can be produced with:
  - `bash scripts/sign_release.sh`
