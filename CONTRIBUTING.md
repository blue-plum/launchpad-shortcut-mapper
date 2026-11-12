# Contributing

Thanks for helping improve Launchpad Shortcut Mapper.

## Development setup

1. Fork and clone the repository.
2. Create a virtual environment: `py -3 -m venv .venv`.
3. Install dependencies: `.\.venv\Scripts\python.exe -m pip install -r requirements.txt`.
4. Run the tests: `.\.venv\Scripts\python.exe -m unittest -v test_core.py`.

## Pull requests

- Keep changes focused and describe the user-facing behaviour.
- Add or update tests when changing profile storage, import/export, shortcut handling, or mappings.
- Test the interface on Windows when changing Tkinter layout or native input handling.
- Do not commit `.venv`, build output, user profiles, icons, or exported `.lpm` files.
- Preserve backward compatibility with existing `%APPDATA%\LaunchpadShortcutMapper\profiles.json` data where practical.

## Bug reports

Please include:

- Windows version
- Launchpad model and MIDI port names
- Application version or commit
- Reproduction steps
- Expected and actual behaviour
- Any displayed error message

Do not attach a profile if it contains sensitive application names or images without reviewing it first.

