# LG TV Tools 0.2.0

LG TV Tools 0.2.0 is a stability and packaging release for KDE Plasma on Kali Linux.

## Highlights

- Flexible LG TV discovery over SSDP/DLNA
- Explicit UPnP error reporting for media playback
- Cleaner, more compact UI
- Release smoke test included
- Local Debian packaging with optional GPG signing

## Notes

- Direct media playback depends on the LG model and on LAN reachability.
- The temporary media URL must be reachable from the TV.
- If client isolation or firewall rules block access, UPnP playback will fail even when discovery works.

## Downloads

- `lg-tv-tools_0.2.0_all.deb`
- `lg-tv-tools_0.2.0_all.deb.sha256`

## Verification

```bash
sha256sum -c lg-tv-tools_0.2.0_all.deb.sha256
```

## Release signing

If you publish signed releases:

```bash
bash scripts/sign_release.sh
```

## Install

```bash
bash scripts/install.sh
```

## Build

```bash
bash scripts/build_deb.sh
```

## Smoke test

```bash
bash scripts/smoke_test.sh
```
