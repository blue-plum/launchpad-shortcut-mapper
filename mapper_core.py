from __future__ import annotations

import json
import hashlib
import os
import zipfile
from dataclasses import dataclass, field, asdict
from pathlib import Path


APP_DIR = Path(os.environ.get("APPDATA", Path.home())) / "LaunchpadShortcutMapper"
CONFIG_PATH = APP_DIR / "profiles.json"


@dataclass
class Binding:
    keys: list[str] = field(default_factory=list)
    label: str = ""
    color: int = 21
    pressed_color: int = 45
    icon: str = ""


@dataclass
class Profile:
    name: str
    executable: str = ""
    bindings: dict[str, Binding] = field(default_factory=dict)


class ProfileStore:
    def __init__(self, path: Path = CONFIG_PATH):
        self.path = path
        self.profiles: list[Profile] = []
        self.last_profile = "Default"
        self.auto_switch = True
        self.input_port = ""
        self.output_port = ""

    def load(self) -> None:
        if not self.path.exists():
            self.profiles = [Profile("Default")]
            return
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
            self.last_profile = raw.get("last_profile", "Default")
            self.auto_switch = bool(raw.get("auto_switch", True))
            self.input_port = raw.get("input_port", "")
            self.output_port = raw.get("output_port", "")
            for item in raw.get("profiles", []):
                bindings = {key: Binding(**value) for key, value in item.get("bindings", {}).items()}
                self.profiles.append(Profile(item["name"], item.get("executable", ""), bindings))
        except (OSError, ValueError, TypeError, KeyError):
            self.profiles = [Profile("Default")]
        if not self.profiles:
            self.profiles = [Profile("Default")]

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "version": 1,
            "last_profile": self.last_profile,
            "auto_switch": self.auto_switch,
            "input_port": self.input_port,
            "output_port": self.output_port,
            "profiles": [asdict(p) for p in self.profiles],
        }
        temp = self.path.with_suffix(".tmp")
        temp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        temp.replace(self.path)

    def get(self, name: str) -> Profile:
        return next((p for p in self.profiles if p.name == name), self.profiles[0])

    def match_executable(self, executable: str) -> Profile | None:
        target = os.path.basename(executable).casefold()
        return next((p for p in self.profiles if p.executable.strip().casefold() == target), None)


MODIFIER_ORDER = ("ctrl", "alt", "shift", "win")
DISPLAY_NAMES = {"ctrl": "Ctrl", "alt": "Alt", "shift": "Shift", "win": "Win",
                 "escape": "Esc", "return": "Enter", "prior": "Page Up", "next": "Page Down",
                 "backspace": "Backspace", "delete": "Delete", "space": "Space", "tab": "Tab"}


def normalize_keys(keys: list[str]) -> list[str]:
    unique = []
    for key in keys:
        key = key.casefold()
        if key not in unique:
            unique.append(key)
    modifiers = [m for m in MODIFIER_ORDER if m in unique]
    return modifiers + [k for k in unique if k not in MODIFIER_ORDER]


def shortcut_text(keys: list[str]) -> str:
    return " + ".join(DISPLAY_NAMES.get(k, k.upper() if len(k) == 1 else k.title()) for k in normalize_keys(keys))


def control_id(kind: str, number: int) -> str:
    return f"{kind}:{number}"


PROFILE_FORMAT = "launchpad-shortcut-profile"


def export_profile(profile: Profile, destination: Path) -> None:
    """Write one portable profile, including its icon files, to a bundle."""
    payload = asdict(profile)
    icon_files: dict[str, Path] = {}
    for binding in payload["bindings"].values():
        icon = binding.get("icon", "")
        source = Path(icon) if icon else None
        if source and source.is_file():
            archive_name = f"icons/{source.name}"
            icon_files[archive_name] = source
            binding["icon"] = archive_name
        else:
            binding["icon"] = ""
    manifest = {"format": PROFILE_FORMAT, "version": 1, "profile": payload}
    destination.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(destination, "w", zipfile.ZIP_DEFLATED) as bundle:
        bundle.writestr("profile.json", json.dumps(manifest, indent=2))
        for archive_name, source in icon_files.items():
            bundle.write(source, archive_name)


def import_profile(source: Path, icons_dir: Path) -> Profile:
    """Read a portable profile without extracting untrusted archive paths."""
    if source.stat().st_size > 50 * 1024 * 1024:
        raise ValueError("Profile bundle is larger than 50 MB.")
    with zipfile.ZipFile(source, "r") as bundle:
        names = set(bundle.namelist())
        if "profile.json" not in names:
            raise ValueError("This file does not contain a Launchpad profile.")
        info = bundle.getinfo("profile.json")
        if info.file_size > 2 * 1024 * 1024:
            raise ValueError("Profile data is unexpectedly large.")
        manifest = json.loads(bundle.read("profile.json").decode("utf-8"))
        if manifest.get("format") != PROFILE_FORMAT or manifest.get("version") != 1:
            raise ValueError("Unsupported Launchpad profile format or version.")
        raw = manifest.get("profile", {})
        if not isinstance(raw.get("name"), str) or not isinstance(raw.get("bindings", {}), dict):
            raise ValueError("The profile data is invalid.")
        if len(raw.get("bindings", {})) > 256:
            raise ValueError("The profile contains too many button mappings.")
        bindings = {}
        icons_dir.mkdir(parents=True, exist_ok=True)
        allowed_fields = {"keys", "label", "color", "pressed_color", "icon"}
        for cid, value in raw.get("bindings", {}).items():
            if not isinstance(value, dict):
                continue
            clean = {key: item for key, item in value.items() if key in allowed_fields}
            icon_name = clean.get("icon", "")
            clean["icon"] = ""
            if isinstance(icon_name, str) and icon_name.startswith("icons/") and icon_name in names:
                icon_info = bundle.getinfo(icon_name)
                if icon_info.file_size > 5 * 1024 * 1024:
                    raise ValueError("An icon in the profile is unexpectedly large.")
                icon_data = bundle.read(icon_name)
                safe_name = f"{hashlib.sha256(icon_data).hexdigest()[:20]}.png"
                destination = icons_dir / safe_name
                destination.write_bytes(icon_data)
                clean["icon"] = str(destination)
            bindings[str(cid)] = Binding(**clean)
        return Profile(raw["name"].strip() or "Imported Profile",
                       os.path.basename(str(raw.get("executable", ""))), bindings)


def unique_profile_name(name: str, existing: list[str]) -> str:
    used = {item.casefold() for item in existing}
    if name.casefold() not in used:
        return name
    index = 2
    while f"{name} ({index})".casefold() in used:
        index += 1
    return f"{name} ({index})"
