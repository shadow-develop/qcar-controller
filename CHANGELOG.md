# QCar Controller — Changelog

## [Unreleased]

## [0.1.0]

Initial working prototype snapshot. Driving and BLE logic and dependency declarations are preserved. Release preparation adds version metadata and updates project naming, script entry points and documentation.

### Included

- QCAR Bluetooth LE discovery, connection and disconnection.
- WASD, arrow-key and mouse-button driving.
- Adjustable motor power, Shift Turbo and headlight control.
- Battery percentage notifications.
- Local movement-command clearing through Space, Escape and the STOP button.
- Windows setup, launch and optional PyInstaller build scripts.
- Repository ignore rules, release documentation and MIT license.
- QCar Controller naming, `qcar_controller.py` entry point and embedded version 0.1.0.

### Hardware testing reported by the project owner

- Older micro-USB battery and newer USB-C battery using the same BLE implementation.
- Driving controls, Turbo, lights, battery reporting and adjustable power.

### Known issues

- Space can activate the focused Connect/Disconnect button.
- Keyboard and movement state can remain stale across focus loss or reconnection.
- Multiple inputs for one action can interfere with each other.
- BLE connection requests can overlap; error handling and cleanup need improvement.
- STOP does not confirm delivery or physical stopping after connection loss.
- Dependency versions are not locked; the UI remains a prototype.

See README.md for details and the planned development sequence. No release date is assigned until the snapshot is tagged.
