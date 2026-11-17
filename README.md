# QCar Controller

Unofficial Windows desktop controller for compatible BrandBase / Shell QCAR Bluetooth LE RC cars, built with Python, Tkinter, Bleak and PyCryptodome.

Repository name: `qcar-controller`.

**v0.1.0 is the initial working prototype.** The original driving and BLE logic and dependency declarations are preserved. Release preparation updates names, version metadata, script entry points and documentation. This version documents the existing behavior, including known issues, before backend refactoring.

This project is not affiliated with, endorsed by, or sponsored by Shell or BrandBase.

## Tested hardware and features

The project owner has tested an older micro-USB battery and a newer USB-C battery with the same BLE implementation. Reported working features include WASD and arrow-key driving, Turbo, lights, battery reporting and adjustable motor power.

These results apply to the two tested battery revisions; compatibility with every QCAR or USB-C revision is not established. The application is named QCar Controller to reflect these results.

## Requirements

- Windows with a working Bluetooth LE adapter.
- Python 3.11 or newer with Tkinter, as requested by the existing setup script. The inspected local environment uses Python 3.12.8; other Python versions have not been verified here.
- A compatible QCAR battery and car.
- Internet access for initial dependency installation.

Runtime dependencies are declared in `requirements.txt`: `bleak>=0.21.1` and `pycryptodome>=3.19.0`. The inspected environment contains Bleak 3.1.0 and PyCryptodome 4.5.0. The requirements are not locked, so a fresh installation can resolve different versions. Tkinter is provided by the Python installation, not by these pip requirements.

## Getting started

1. Enable Bluetooth on the computer and switch on the battery in the car.
2. Close Shell Racing on your phone so it does not hold the BLE connection.
3. Run `setup.bat`. It creates `.venv`, installs dependencies and launches the application.
4. Click **Scan**, select a `QCAR-...` device and click **Connect**.
5. Make sure the application receives keyboard input before driving. Read the known issues below, especially the Space/focus conflict.

For subsequent launches, run `run.bat`.

## Controls

| Action | Input |
| --- | --- |
| Forward | W / Up |
| Reverse | S / Down |
| Steer left | A / Left |
| Steer right | D / Right |
| Turbo (100% command power) | Hold either Shift key |
| Clear movement commands | Space / Escape / STOP button |
| Toggle lights | L / Lights checkbox |
| Normal motor power | Slider, 22–100; default 80 |

The directional UI buttons also support mouse hold. The power setting is a command value, not a measured vehicle speed. Battery percentage is displayed when a recognized notification arrives.

## Known issues

- Space can activate a focused Connect/Disconnect button in addition to requesting a stop.
- WASD can stop responding after some disconnect/reconnect scenarios while arrow keys continue working.
- Pressed-key and movement state are not reliably cleared on disconnect or focus loss. Stale movement state may carry into a later connection.
- Keyboard input depends on key symbols; keyboard layout and Shift transitions can affect handling.
- Inputs mapped to the same direction do not combine independently: releasing W can clear forward movement while Up is still held.
- Repeated connection requests can overlap. BLE error handling and connection cleanup need improvement.
- STOP clears local movement state and relies on a subsequent BLE write. It is not confirmation that the car has physically stopped, especially after a connection failure.
- The UI is a prototype. Settings persistence, configurable bindings, gamepads and multi-car control are not implemented.

For initial testing, keep the wheels clear of the surface and the battery switch accessible. Firmware behavior after loss of commands has not been established by this release documentation.

## Optional EXE build

Run `make_exe.bat` after confirming the Python application works. It installs PyInstaller and builds `dist/QCarController.exe` using one-file/windowed mode. PyInstaller is a build dependency and is not pinned by the script. This preparation does not independently verify the EXE build.

Build outputs and the virtual environment are excluded from Git. Any future distributed EXE should be attached to a release rather than committed as source.

## Current architecture

All application code is in `qcar_controller.py`:

- `App` owns the Tkinter UI and keyboard/mouse handling on the main thread.
- `BleWorker` runs an asyncio event loop on a background thread for BLE scanning, connections, notifications and periodic writes.
- A thread-safe queue carries worker events to the UI; a lock protects movement state.
- `_make_packet()` encodes a 16-byte control packet and encrypts it with AES-128-ECB. The control loop pauses 50 ms between completed writes.

Devices are discovered by their `QCAR-` name prefix. There is currently one command layout and no automatic capability detection.

## Versioning and development direction

The initial snapshot is identified by Git tag `v0.1.0`; the application declares `__version__ = "0.1.0"` in `qcar_controller.py`. Release changes are recorded in [CHANGELOG.md](CHANGELOG.md).

After this snapshot, the intended sequence is to improve input/connection reliability and separate backend responsibilities, then redesign the UI. Configurable bindings, persistent settings, gamepads, analog throttle, multiple cars and capability diagnostics are future work, not release promises.

## Protocol references and credits

The original prototype documentation cites these community reverse-engineering resources:

- [scrool/qcar-docs](https://github.com/scrool/qcar-docs)
- [DarkNikGr Web Bluetooth controller](https://gist.github.com/DarkNikGr/76bcf9bfbb34857bfa04ff4efdda768c)
- [AMasetti/shell-motorsport-rc-lib](https://github.com/AMasetti/shell-motorsport-rc-lib)

These references are not runtime dependencies. Their code and documentation retain their respective authorship and licenses.

## License

Licensed under the [MIT License](LICENSE).
