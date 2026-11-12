# Launchpad Shortcut Mapper

Turn a Novation Launchpad Mini MK3 into a programmable Windows shortcut controller.

Launchpad Shortcut Mapper provides a visual editor for assigning keyboard shortcuts, LED colours, and reference icons to every pad. Profiles can switch automatically with the foreground application and can be exported as portable `.lpm` files for sharing.

## Highlights

- Visual editor for the 8×8 pad grid, top buttons, and side buttons
- MIDI Learn for selecting controls from the physical Launchpad
- Keyboard shortcut recording and native Windows input injection
- Separate unpressed and pressed LED colours
- Optional reference icons with colour-changing borders
- Per-application profiles with foreground-app switching
- Import, export, rename, and share individual profiles
- Connection animation and live LED feedback
- Portable Windows executable builds with Python bundled

## Requirements

- Windows 10 or Windows 11
- Novation Launchpad Mini MK3 connected over USB
- Novation USB/MIDI driver where required by Windows
- Python 3.11+ only when running from source

Close Ableton Live or any other program holding the Launchpad MIDI ports before connecting from this application.

## Running from source

1. Install Python 3.11 or newer.
2. Clone the repository.
3. Double-click `run.bat`.

The launcher creates a local virtual environment and installs the dependencies on first use. Alternatively:

```powershell
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe app.py
```

## Basic use

1. Choose the Launchpad MIDI input and output ports.
2. Select **Connect**.
3. Click a control in the visual layout, or enable **Learn** and press it physically.
4. Record a keyboard shortcut and optionally add a label.
5. Use colour assignment mode to paint unpressed and pressed LED colours onto controls.
6. Use icon assignment mode to paint reference images onto controls in the software layout.
7. Create profiles and associate them with executable names such as `photoshop.exe` or `obs64.exe`.

## Sharing profiles

Select **Export profile** to create one `.lpm` bundle containing the active profile's shortcuts, labels, colours, application association, and icons. Another user can load it with **Import profile**. Imported name clashes are resolved automatically.

Only import profile files from people you trust. The importer validates the bundle structure and limits file sizes, but shared configuration should still be treated like any other downloaded file.

## Data storage

Local settings and copied icons are stored in:

```text
%APPDATA%\LaunchpadShortcutMapper
```

The main configuration is `profiles.json`. Exported profiles use the `.lpm` extension.

## Keyboard and security notes

- Shortcuts are sent to the application that currently has focus.
- Windows prevents a normal application from injecting input into an elevated application. Run both at the same privilege level.
- Corporate application-control policies may block unsigned executables even when they are self-contained.
- Classic Windows MIDI ports are commonly single-client; another application may prevent connection.

## Development

Run the test suite with:

```powershell
python -m unittest -v test_core.py
```

The project uses Tkinter for the interface, `python-rtmidi` for MIDI I/O, Pillow for image handling, and the Windows `SendInput` API for keyboard shortcuts.

## Building a portable executable

Install PyInstaller, then build from the project directory:

```powershell
python -m pip install pyinstaller
python -m PyInstaller --noconfirm --clean --windowed --onefile `
  --name LaunchpadShortcutMapper `
  --collect-all rtmidi --collect-all PIL app.py
```

The executable is created in `dist/`.

## Contributing

Bug reports and focused pull requests are welcome. See [CONTRIBUTING.md](CONTRIBUTING.md) for setup and submission guidance.

## Licence

Released under the [MIT Licence](LICENSE).

This is an independent community project and is not affiliated with or endorsed by Novation or Focusrite. Launchpad and Novation are trademarks of their respective owners.

