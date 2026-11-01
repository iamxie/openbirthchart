# Open BirthChart

English · [繁體中文](README.md)

**This branch is the unmerged, unreleased 0.7.0-dev development version.** The new [Sky timeline](docs/SKY_TIMELINE.md) scans every ten minutes and locally refines retrograde and aspect events, with interval bands, exact-event markers, real progress and cancellation. Both modes share application-wide aspect-orb settings. Download links below still refer to the published 0.6.7 release, which does not include this feature.

A Windows desktop natal-chart application powered by LibEphemeris, with Traditional Chinese and English interfaces, fourteen house systems, planetary positions, house cusps, aspects and offline reports.

**v0.6.7 is now available.** [Download the Windows application and full corresponding source](https://github.com/iamxie/openbirthchart/releases/tag/v0.6.7).

## Download

Get `OpenBirthChart-0.6.7-windows-x64.zip` from [Releases](https://github.com/iamxie/openbirthchart/releases), extract the entire folder and run `OpenBirthChart.exe`. Python and ephemeris data are included. Keep the folder intact. The release also provides SHA-256 checksums and `OpenBirthChart-0.6.7-source.zip` with corresponding source. Only Windows x64 binaries are provided. The application is not code-signed.

## Features and limits

- Fourteen house systems, actual/zero ecliptic latitude for house placement, configurable aspect orbs and local profiles.
- PNG/SVG charts and self-contained HTML reports, printable to PDF from a browser.
- Consistent zodiac outlines in English charts and position tables, with readable sign names and degrees.
- Invalid house numbers stop chart generation/export. Exact-cusp residuals are corrected only with the required geometric evidence.
- Leap-second inputs are rejected without changing the input time. Ambiguous/degenerate Polich–Page placement rejects the whole chart. Known individual Koch undefined placements remain visibly undefined.
- High-latitude and other geometric limitations apply. Azimuth numbering follows this application's cusp geometry; some results differ from Swiss. No universal equivalence is claimed.

## Privacy

Profiles and settings are stored in `%USERPROFILE%\Documents\openbirthchart\data.sqlite`, outside the installation folder. This database is not encrypted and may contain names, birth details, notes and the optional geocoding key. Treat backups accordingly.

Calculation works offline, with no automatic chart uploads or telemetry. Optional address lookup sends the entered address and key to geocode.maps.co; the key is saved locally. Opening a map uses the browser. Manual coordinates require no API key.

## Development

On Windows x64 with PowerShell, Git and uv, run `./setup-desktop.ps1`, then `./launch-desktop.ps1`. Initial provisioning needs network access; dependency versions and data hashes are pinned. The complete source archive includes runtime data and upstream source archives. Git checkouts download the same pinned data.

See [building](docs/BUILDING.md), [dependency upgrades](docs/DEPENDENCY_UPGRADES.md), [validation](docs/VALIDATION.md), [bilingual articles](docs/README.md) and [release notes](docs/releases/v0.6.7.md). Large immutable validation archives are included in the complete source ZIP rather than the small Git working tree. Swiss/pyswisseph is used only in a separate validation environment, not as a desktop runtime dependency.

## License

Copyright (C) 2026 OpenBirthChart contributors. Original code is licensed under [AGPL-3.0-only](LICENSE), WITHOUT ANY WARRANTY. Third-party materials retain their own terms: see [NOTICE](NOTICE.md), [third-party notices](THIRD_PARTY_DESKTOP.md) and `licenses/`. The application's About and License button provides offline notices and the full license text.
