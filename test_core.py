import tempfile
import unittest
from pathlib import Path

from mapper_core import (Binding, Profile, ProfileStore, export_profile,
                         import_profile, normalize_keys, shortcut_text,
                         unique_profile_name)


class CoreTests(unittest.TestCase):
    def test_shortcut_normalization(self):
        self.assertEqual(normalize_keys(["K", "shift", "ctrl", "shift"]), ["ctrl", "shift", "k"])
        self.assertEqual(shortcut_text(["k", "shift", "ctrl"]), "Ctrl + Shift + K")

    def test_round_trip_and_app_match(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "profiles.json"
            store = ProfileStore(path)
            store.profiles = [Profile("Browser", "chrome.exe", {"note:11": Binding(["ctrl", "l"], "Address")})]
            store.last_profile = "Browser"; store.save()
            loaded = ProfileStore(path); loaded.load()
            self.assertEqual(loaded.get("Browser").bindings["note:11"].keys, ["ctrl", "l"])
            self.assertEqual(loaded.get("Browser").bindings["note:11"].pressed_color, 45)
            self.assertEqual(loaded.match_executable(r"C:\Program Files\Chrome\CHROME.EXE").name, "Browser")

    def test_old_profile_gets_default_pressed_colour(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "profiles.json"
            path.write_text('{"profiles":[{"name":"Old","bindings":{"note:11":{"keys":["a"],"label":"","color":5}}}]}')
            store = ProfileStore(path); store.load()
            self.assertEqual(store.get("Old").bindings["note:11"].pressed_color, 45)

    def test_colour_pair_round_trip(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "profiles.json"
            store = ProfileStore(path)
            store.profiles = [Profile("Colours", bindings={"note:42": Binding(color=5, pressed_color=53)})]
            store.save()
            loaded = ProfileStore(path); loaded.load()
            binding = loaded.get("Colours").bindings["note:42"]
            self.assertEqual((binding.color, binding.pressed_color), (5, 53))

    def test_icon_round_trip(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "profiles.json"
            store = ProfileStore(path)
            store.profiles = [Profile("Icons", bindings={"note:42": Binding(icon=r"C:\icons\save.png")})]
            store.save()
            loaded = ProfileStore(path); loaded.load()
            self.assertEqual(loaded.get("Icons").bindings["note:42"].icon, r"C:\icons\save.png")

    def test_portable_profile_bundle_includes_icon(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            icon = root / "source.png"; icon.write_bytes(b"fake-png-data")
            profile = Profile("Editing", "editor.exe", {
                "note:11": Binding(["ctrl", "s"], "Save", 5, 53, str(icon))
            })
            bundle = root / "editing.lpm"
            export_profile(profile, bundle)
            imported = import_profile(bundle, root / "imported-icons")
            binding = imported.bindings["note:11"]
            self.assertEqual((imported.name, imported.executable), ("Editing", "editor.exe"))
            self.assertEqual((binding.keys, binding.color, binding.pressed_color), (["ctrl", "s"], 5, 53))
            self.assertTrue(Path(binding.icon).is_file())
            self.assertEqual(Path(binding.icon).read_bytes(), b"fake-png-data")

    def test_imported_profile_gets_unique_name(self):
        self.assertEqual(unique_profile_name("Editing", ["Default", "Editing", "Editing (2)"]), "Editing (3)")


if __name__ == "__main__":
    unittest.main()
