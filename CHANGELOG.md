# Changelog

All notable changes are documented here. Future releases use the categories Added, Changed, Fixed, Removed, and Security as applicable.

## 0.2.0

### Added

- Automatic and manual Ford OAuth flows.
- Additional Ford telemetry entities and diagnostics.
- Optional FordConnect API handling for vehicle health, wallbox, and EV schedule data.

### Changed

- Improved refresh handling for optional endpoints while prioritizing vehicle telemetry.

### Fixed

- Kept structured telemetry values, including heading and acceleration, compatible with Home Assistant entity states.

## 0.1.0

### Added

- Initial Ford Connect integration with Ford OAuth, garage discovery, and vehicle telemetry.
