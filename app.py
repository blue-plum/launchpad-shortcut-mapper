from __future__ import annotations

import hashlib
import os
import shutil
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog, filedialog
from pathlib import Path

from mapper_core import (APP_DIR, Binding, Profile, ProfileStore, control_id,
                         export_profile, import_profile, normalize_keys,
                         shortcut_text, unique_profile_name)
from windows_keys import foreground_executable, send_shortcut

try:
    from PIL import Image, ImageTk, ImageOps
except ImportError:
    Image = ImageTk = ImageOps = None

try:
    from midi_device import LaunchpadMidi
    MIDI_ERROR = ""
except Exception as exc:
    LaunchpadMidi = None
    MIDI_ERROR = str(exc)


BG, PANEL, CARD = "#10131a", "#171b24", "#202632"
TEXT, MUTED, ACCENT, GREEN, RED = "#f2f5fa", "#9aa6b6", "#8b5cf6", "#34d399", "#fb7185"
PAD_OFF, PAD_ON, PAD_SELECTED = "#303846", "#6d4bd1", "#c4b5fd"

PALETTE = [
    ("Off", 0, "#303846"), ("White", 3, "#f4f4f5"),
    ("Red", 5, "#ef4444"), ("Coral", 9, "#fb7185"),
    ("Orange", 10, "#f97316"), ("Amber", 13, "#f59e0b"),
    ("Yellow", 17, "#facc15"), ("Lime", 21, "#84cc16"),
    ("Green", 22, "#22c55e"), ("Mint", 29, "#34d399"),
    ("Cyan", 37, "#22d3ee"), ("Sky", 41, "#38bdf8"),
    ("Blue", 45, "#3b82f6"), ("Purple", 49, "#8b5cf6"),
    ("Magenta", 53, "#d946ef"), ("Pink", 57, "#ec4899"),
]
PALETTE_RGB = {number: rgb for _name, number, rgb in PALETTE}


class MapperApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Launchpad Shortcut Mapper")
        self.geometry("1120x760")
        self.minsize(980, 680)
        self.configure(bg=BG)
        self.store = ProfileStore(); self.store.load()
        self.profile = self.store.get(self.store.last_profile)
        self.selected = "note:11"
        self.learning = False
        self.recording = False
        self.recorded_keys = []
        self.colour_assignment = False
        self.icon_assignment = False
        self.icon_brush = ""
        self.brush_unpressed = 21
        self.brush_pressed = 45
        self.colour_swatches = {False: {}, True: {}}
        self.animation_generation = 0
        self.pad_widgets = {}
        self.pad_frames = {}
        self.pad_sizes = {}
        self.icon_images = {}
        self.midi = LaunchpadMidi(self._midi_thread_event) if LaunchpadMidi else None
        self._style(); self._build(); self._refresh_ports(); self._refresh_all()
        self.protocol("WM_DELETE_WINDOW", self._close)
        self.after(800, self._poll_foreground)

    def _style(self):
        s = ttk.Style(self); s.theme_use("clam")
        s.configure("TCombobox", fieldbackground=CARD, background=CARD, foreground=TEXT, arrowcolor=TEXT)
        s.configure("TCheckbutton", background=PANEL, foreground=TEXT)

    def _label(self, parent, text, size=10, color=TEXT, bold=False, **kw):
        return tk.Label(parent, text=text, bg=parent.cget("bg"), fg=color,
                        font=("Segoe UI", size, "bold" if bold else "normal"), **kw)

    def _button(self, parent, text, command, accent=False, **kw):
        return tk.Button(parent, text=text, command=command, bg=ACCENT if accent else CARD, fg=TEXT,
                         activebackground="#7656d8", activeforeground=TEXT, relief="flat", bd=0,
                         font=("Segoe UI", 10, "bold"), padx=14, pady=8, cursor="hand2", **kw)

    def _build(self):
        header = tk.Frame(self, bg=PANEL, padx=22, pady=15); header.pack(fill="x")
        self._label(header, "Launchpad Shortcut Mapper", 17, bold=True).pack(side="left")
        self.status = self._label(header, "●  Disconnected", 10, RED); self.status.pack(side="right")

        connection = tk.Frame(self, bg=PANEL, padx=22, pady=8); connection.pack(fill="x")
        self._label(connection, "MIDI input", color=MUTED).pack(side="left")
        self.in_var = tk.StringVar(); self.in_combo = ttk.Combobox(connection, textvariable=self.in_var, width=31, state="readonly")
        self.in_combo.pack(side="left", padx=(8, 18))
        self._label(connection, "MIDI output", color=MUTED).pack(side="left")
        self.out_var = tk.StringVar(); self.out_combo = ttk.Combobox(connection, textvariable=self.out_var, width=31, state="readonly")
        self.out_combo.pack(side="left", padx=8)
        self._button(connection, "↻", self._refresh_ports).pack(side="left", padx=4)
        self.connect_btn = self._button(connection, "Connect", self._connect, accent=True); self.connect_btn.pack(side="left", padx=4)

        body = tk.Frame(self, bg=BG, padx=22, pady=20); body.pack(fill="both", expand=True)
        left = tk.Frame(body, bg=PANEL, padx=22, pady=18); left.pack(side="left", fill="both", expand=True)
        right = tk.Frame(body, bg=PANEL, width=360, padx=22, pady=18); right.pack(side="right", fill="y", padx=(18,0)); right.pack_propagate(False)
        self._build_grid(left); self._build_editor(right)

    def _build_grid(self, parent):
        top = tk.Frame(parent, bg=PANEL); top.pack(fill="x", pady=(0, 12))
        self._label(top, "CONTROLLER", 10, MUTED, True).pack(side="left")
        self.learn_btn = self._button(top, "Learn: off", self._toggle_learn); self.learn_btn.pack(side="right")
        grid = tk.Frame(parent, bg=PANEL); grid.pack(expand=True)
        for col in range(8):
            self._pad(grid, 0, col, "cc", 91 + col, small=True)
        for visual_row in range(8):
            note_row = 8 - visual_row
            for col in range(8):
                self._pad(grid, visual_row + 1, col, "note", note_row * 10 + col + 1)
            self._pad(grid, visual_row + 1, 8, "note", note_row * 10 + 9, small=True)
        self._label(parent, "Click a control, or enable Learn and press it on the Launchpad.", 9, MUTED).pack(pady=(14,0))

    def _pad(self, parent, row, col, kind, number, small=False):
        cid = control_id(kind, number)
        border = tk.Frame(parent, bg=PAD_OFF, bd=0, highlightthickness=0)
        border.grid(row=row, column=col, padx=5, pady=5)
        btn = tk.Button(border, text="", command=lambda c=cid: self._grid_press(c), bg=PAD_OFF,
                        activebackground=PAD_SELECTED, relief="flat", bd=0, cursor="hand2",
                        width=3 if small else 5, height=1 if small else 2)
        btn.pack(padx=4, pady=4)
        self.pad_widgets[cid] = btn
        self.pad_frames[cid] = border
        self.pad_sizes[cid] = small

    def _build_editor(self, parent):
        self._label(parent, "PROFILE", 10, MUTED, True).pack(anchor="w")
        row = tk.Frame(parent, bg=PANEL); row.pack(fill="x", pady=(8,10))
        self.profile_var = tk.StringVar(); self.profile_combo = ttk.Combobox(row, textvariable=self.profile_var, state="readonly", width=22)
        self.profile_combo.pack(side="left", fill="x", expand=True); self.profile_combo.bind("<<ComboboxSelected>>", self._change_profile)
        self._button(row, "+", self._new_profile).pack(side="left", padx=(6,0))
        self._button(row, "−", self._delete_profile).pack(side="left", padx=(4,0))
        transfer = tk.Frame(parent, bg=PANEL); transfer.pack(fill="x", pady=(0,10))
        self._button(transfer, "Export profile", self._export_profile).pack(side="left", fill="x", expand=True)
        self._button(transfer, "Import profile", self._import_profile).pack(side="left", fill="x", expand=True, padx=(6,0))
        self._button(transfer, "Rename", self._rename_profile).pack(side="left", fill="x", expand=True, padx=(6,0))
        self._label(parent, "Use when foreground app is", 9, MUTED).pack(anchor="w")
        self.exe_var = tk.StringVar(); exe = tk.Entry(parent, textvariable=self.exe_var, bg=CARD, fg=TEXT, insertbackground=TEXT, relief="flat", font=("Segoe UI",10))
        exe.pack(fill="x", ipady=7, pady=(5,6)); exe.bind("<FocusOut>", lambda _e: self._save_profile_settings())
        self.auto_var = tk.BooleanVar(value=self.store.auto_switch)
        ttk.Checkbutton(parent, text="Auto-switch profiles", variable=self.auto_var, command=self._save_profile_settings).pack(anchor="w")
        tk.Frame(parent, bg="#333a48", height=1).pack(fill="x", pady=18)

        self.control_title = self._label(parent, "PAD", 10, MUTED, True); self.control_title.pack(anchor="w")
        self.shortcut = self._label(parent, "Not assigned", 19, TEXT, True, wraplength=310, justify="left")
        self.shortcut.pack(anchor="w", pady=(12,6))
        self.label_var = tk.StringVar(); label_entry = tk.Entry(parent, textvariable=self.label_var, bg=CARD, fg=TEXT, insertbackground=TEXT, relief="flat", font=("Segoe UI",10))
        label_entry.pack(fill="x", ipady=7, pady=(8,12)); label_entry.bind("<FocusOut>", lambda _e: self._save_label())
        self.record_btn = self._button(parent, "Record shortcut", self._record, accent=True); self.record_btn.pack(fill="x", pady=4)
        self._button(parent, "Clear assignment", self._clear).pack(fill="x", pady=4)
        self._label(parent, "LED COLOURS", 10, MUTED, True).pack(anchor="w", pady=(16,6))
        self.colour_mode_btn = self._button(parent, "Start colour assignment", self._toggle_colour_assignment)
        self.colour_mode_btn.pack(fill="x", pady=(0,8))
        colour_row = tk.Frame(parent, bg=PANEL); colour_row.pack(fill="x")
        for title, pressed in (("Unpressed", False), ("Pressed", True)):
            column = tk.Frame(colour_row, bg=PANEL)
            column.pack(side="left", fill="x", expand=True, padx=(0,8) if not pressed else (8,0))
            caption = self._label(column, title, 9, MUTED)
            caption.pack(anchor="w")
            if pressed: self.pressed_colour_caption = caption
            else: self.unpressed_colour_caption = caption
            box = tk.Frame(column, bg=PANEL); box.pack(anchor="w", pady=(5,0))
            for index, (name, number, rgb) in enumerate(PALETTE):
                swatch = tk.Button(box, bg=rgb, activebackground=rgb, relief="flat", bd=0,
                                   width=2, height=1, cursor="hand2",
                                   command=lambda n=number, p=pressed: self._set_colour(p, n))
                swatch.grid(row=index // 4, column=index % 4, padx=1, pady=1)
                swatch.configure(takefocus=False)
                self.colour_swatches[pressed][number] = swatch
        self._label(parent, "BUTTON ICONS", 10, MUTED, True).pack(anchor="w", pady=(14,6))
        self.icon_mode_btn = self._button(parent, "Start icon assignment", self._toggle_icon_assignment)
        self.icon_mode_btn.pack(fill="x", pady=(0,5))
        icon_buttons = tk.Frame(parent, bg=PANEL); icon_buttons.pack(fill="x")
        self._button(icon_buttons, "Choose image…", self._choose_icon).pack(side="left", fill="x", expand=True)
        self._button(icon_buttons, "Erase icons", self._choose_no_icon).pack(side="left", fill="x", expand=True, padx=(6,0))
        self.icon_caption = self._label(parent, "Selected image: none", 9, MUTED, wraplength=310, justify="left")
        self.icon_caption.pack(anchor="w", pady=(5,0))
        self.hint = self._label(parent, "", 9, MUTED, wraplength=310, justify="left"); self.hint.pack(anchor="w", pady=12)

    def _refresh_ports(self):
        if not self.midi:
            self.status.configure(text="●  MIDI package missing", fg=RED); return
        try:
            ins, outs = self.midi.ports(); self.in_combo["values"] = ins; self.out_combo["values"] = outs
            self.in_var.set(self.store.input_port if self.store.input_port in ins else self._prefer_port(ins))
            self.out_var.set(self.store.output_port if self.store.output_port in outs else self._prefer_port(outs))
        except Exception as exc: self.status.configure(text=f"●  {exc}", fg=RED)

    @staticmethod
    def _prefer_port(ports):
        return next((p for p in ports if "MIDIIN2" in p.upper() or "DAW" in p.upper()),
                    next((p for p in ports if "LAUNCHPAD" in p.upper()), ports[0] if ports else ""))

    def _connect(self):
        if self.midi and self.midi.input:
            self.animation_generation += 1
            self.midi.disconnect(); self.status.configure(text="●  Disconnected", fg=RED); self.connect_btn.configure(text="Connect"); return
        if not self.in_var.get() or not self.out_var.get():
            messagebox.showwarning("No MIDI port", "Connect the Launchpad, then click the refresh button."); return
        try:
            self.midi.connect(self.in_var.get(), self.out_var.get())
            self.store.input_port, self.store.output_port = self.in_var.get(), self.out_var.get(); self.store.save()
            self.status.configure(text="●  Connected", fg=GREEN); self.connect_btn.configure(text="Disconnect"); self._connection_animation()
        except Exception as exc: messagebox.showerror("Could not connect", str(exc))

    def _midi_thread_event(self, kind, number, pressed):
        self.after(0, lambda: self._midi_event(kind, number, pressed))

    def _midi_event(self, kind, number, pressed):
        cid = control_id(kind, number)
        if self.icon_assignment:
            if pressed:
                self._apply_icon(cid)
                binding = self.profile.bindings.get(cid)
                if binding:
                    self.midi.set_led(kind, number, binding.pressed_color)
                    if cid in self.pad_widgets: self._paint_pad(cid, True)
            else:
                binding = self.profile.bindings.get(cid)
                if binding:
                    self.midi.set_led(kind, number, binding.color)
                    if cid in self.pad_widgets: self._paint_pad(cid, False)
            return
        if self.colour_assignment:
            if pressed:
                self._apply_colour(cid)
                self.midi.set_led(kind, number, self.brush_pressed)
                if cid in self.pad_widgets: self._paint_pad(cid, True)
            else:
                binding = self.profile.bindings.get(cid)
                if binding:
                    self.midi.set_led(kind, number, binding.color)
                    if cid in self.pad_widgets: self._paint_pad(cid, False)
            return
        if self.learning and pressed: self._select(cid)
        binding = self.profile.bindings.get(cid)
        if binding:
            self.midi.set_led(kind, number, binding.pressed_color if pressed else binding.color)
            if cid in self.pad_widgets: self._paint_pad(cid, pressed)
        if pressed and binding and binding.keys:
            try: send_shortcut(binding.keys)
            except Exception as exc: self.status.configure(text=f"●  Shortcut failed: {exc}", fg=RED)

    def _select(self, cid):
        self.selected = cid; self._refresh_editor(); self._refresh_pads()

    def _grid_press(self, cid):
        if self.icon_assignment: self._apply_icon(cid)
        elif self.colour_assignment: self._apply_colour(cid)
        else: self._select(cid)

    def _record(self):
        self.recording = True; self.recorded_keys = []
        self.record_btn.configure(text="Press shortcut now…", bg=RED)
        self.hint.configure(text="Press the key combination. Release the final key to save. Press Esc alone to cancel.")
        self.bind_all("<KeyPress>", self._capture_press); self.bind_all("<KeyRelease>", self._capture_release)
        self.focus_force()

    def _key_name(self, event):
        aliases = {"Control_L":"ctrl", "Control_R":"ctrl", "Alt_L":"alt", "Alt_R":"alt",
                   "Shift_L":"shift", "Shift_R":"shift", "Win_L":"win", "Win_R":"win",
                   "Super_L":"win", "Super_R":"win", "Escape":"escape", "Return":"return",
                   "BackSpace":"backspace", "Prior":"prior", "Next":"next"}
        return aliases.get(event.keysym, event.keysym.casefold())

    def _capture_press(self, event):
        if not self.recording: return
        key = self._key_name(event)
        if key not in self.recorded_keys: self.recorded_keys.append(key)
        self.shortcut.configure(text=shortcut_text(self.recorded_keys)); return "break"

    def _capture_release(self, event):
        if not self.recording: return
        key = self._key_name(event)
        if key in ("ctrl", "alt", "shift", "win") and all(k in ("ctrl","alt","shift","win") for k in self.recorded_keys): return "break"
        keys = normalize_keys(self.recorded_keys); self._stop_recording()
        if keys == ["escape"]: self._refresh_editor(); return "break"
        old = self.profile.bindings.get(self.selected)
        self.profile.bindings[self.selected] = Binding(
            keys=keys, label=self.label_var.get().strip(),
            color=old.color if old else 21,
            pressed_color=old.pressed_color if old else 45,
        )
        self.store.save(); self._refresh_all(); return "break"

    def _stop_recording(self):
        self.recording = False; self.unbind_all("<KeyPress>"); self.unbind_all("<KeyRelease>")
        self.record_btn.configure(text="Record shortcut", bg=ACCENT); self.hint.configure(text="")

    def _clear(self):
        self.profile.bindings.pop(self.selected, None); self.store.save(); self._refresh_all()

    def _set_colour(self, pressed, number):
        if pressed: self.brush_pressed = number
        else: self.brush_unpressed = number
        self._refresh_palette_display()
        if not self.colour_assignment:
            self.hint.configure(text="Press ‘Start colour assignment’, then press the controls that should receive this colour pair.")

    def _toggle_colour_assignment(self):
        if not self.colour_assignment and self.icon_assignment:
            self._stop_icon_assignment()
        self.colour_assignment = not self.colour_assignment
        if self.colour_assignment:
            binding = self.profile.bindings.get(self.selected)
            if binding:
                self.brush_unpressed, self.brush_pressed = binding.color, binding.pressed_color
            self.colour_mode_btn.configure(text="Stop colour assignment", bg=RED)
            self.hint.configure(text="Choose both colours, then press physical or on-screen Launchpad buttons. Change the colours and continue painting; press Stop when finished.")
        else:
            self.colour_mode_btn.configure(text="Start colour assignment", bg=CARD)
            self.hint.configure(text="")
        self._refresh_palette_display()

    def _toggle_icon_assignment(self):
        if self.icon_assignment:
            self._stop_icon_assignment(); return
        if self.colour_assignment:
            self.colour_assignment = False
            self.colour_mode_btn.configure(text="Start colour assignment", bg=CARD)
        binding = self.profile.bindings.get(self.selected)
        self.icon_brush = binding.icon if binding else ""
        self.icon_assignment = True
        self.icon_mode_btn.configure(text="Stop icon assignment", bg=RED)
        self._refresh_icon_caption()
        self.hint.configure(text="Choose an image, then press physical or on-screen Launchpad buttons. Choose another image and continue painting; press Stop when finished.")

    def _stop_icon_assignment(self):
        self.icon_assignment = False
        self.icon_mode_btn.configure(text="Start icon assignment", bg=CARD)
        self.hint.configure(text="")

    def _choose_icon(self):
        path = filedialog.askopenfilename(
            parent=self, title="Choose button icon",
            filetypes=[("Image files", "*.png *.jpg *.jpeg *.bmp *.gif *.webp"), ("All files", "*.*")],
        )
        if not path: return
        try:
            if os.path.getsize(path) > 20 * 1024 * 1024:
                raise ValueError("Please choose an image smaller than 20 MB.")
            APP_DIR.joinpath("icons").mkdir(parents=True, exist_ok=True)
            with open(path, "rb") as source_file:
                digest = hashlib.sha256(source_file.read()).hexdigest()[:20]
            destination = APP_DIR / "icons" / f"{digest}.png"
            if Image:
                with Image.open(path) as source:
                    normalised = ImageOps.contain(source.convert("RGBA"), (256, 256), Image.Resampling.LANCZOS)
                    normalised.save(destination, "PNG", optimize=True)
            else:
                if not path.casefold().endswith(".png"):
                    raise ValueError("This build requires a PNG image.")
                shutil.copy2(path, destination)
            self.icon_brush = str(destination)
            self._refresh_icon_caption()
            if not self.icon_assignment:
                self.hint.configure(text="Press ‘Start icon assignment’, then press the controls that should receive this image.")
        except Exception as exc:
            messagebox.showerror("Could not use image", str(exc))

    def _choose_no_icon(self):
        self.icon_brush = ""
        self._refresh_icon_caption()
        if not self.icon_assignment:
            self.hint.configure(text="Start icon assignment and press controls to remove their icons.")

    def _refresh_icon_caption(self):
        name = os.path.basename(self.icon_brush) if self.icon_brush else "none (erase)"
        self.icon_caption.configure(text=f"Selected image: {name}")

    def _apply_icon(self, cid):
        binding = self.profile.bindings.get(cid)
        if not binding:
            binding = Binding(); self.profile.bindings[cid] = binding
        binding.icon = self.icon_brush
        self.selected = cid
        self.store.save(); self._refresh_editor(); self._refresh_pads(); self._update_leds()

    def _apply_colour(self, cid):
        binding = self.profile.bindings.get(cid)
        if not binding:
            binding = Binding()
            self.profile.bindings[cid] = binding
        binding.color = self.brush_unpressed
        binding.pressed_color = self.brush_pressed
        self.selected = cid
        self.store.save(); self._refresh_editor(); self._refresh_pads(); self._update_leds()

    def _save_label(self):
        label = self.label_var.get().strip()
        binding = self.profile.bindings.get(self.selected)
        if not binding and label:
            binding = Binding(); self.profile.bindings[self.selected] = binding
        if binding:
            binding.label = label; self.store.save(); self._refresh_pads(); self._update_leds()

    def _toggle_learn(self):
        self.learning = not self.learning; self.learn_btn.configure(text=f"Learn: {'on' if self.learning else 'off'}", bg=ACCENT if self.learning else CARD)

    def _change_profile(self, _event=None):
        self._activate_profile(self.profile_var.get())

    def _activate_profile(self, name):
        self.profile = self.store.get(name); self.store.last_profile = self.profile.name; self.store.save(); self._refresh_all()

    def _new_profile(self):
        name = simpledialog.askstring("New profile", "Profile name:", parent=self)
        if not name or any(p.name.casefold() == name.strip().casefold() for p in self.store.profiles): return
        self.store.profiles.append(Profile(name.strip())); self._activate_profile(name.strip())

    def _delete_profile(self):
        if len(self.store.profiles) == 1: messagebox.showinfo("Keep one profile", "At least one profile is required."); return
        if not messagebox.askyesno("Delete profile", f"Delete ‘{self.profile.name}’ and all its assignments?"): return
        self.store.profiles.remove(self.profile); self._activate_profile(self.store.profiles[0].name)

    def _rename_profile(self):
        name = simpledialog.askstring("Rename profile", "New profile name:",
                                      initialvalue=self.profile.name, parent=self)
        if not name: return
        name = name.strip()
        if not name or name == self.profile.name: return
        if any(item is not self.profile and item.name.casefold() == name.casefold() for item in self.store.profiles):
            messagebox.showwarning("Name already used", "Please choose a different profile name.")
            return
        self.profile.name = name
        self.store.last_profile = name
        self.store.save(); self._refresh_all()

    def _export_profile(self):
        suggested = "".join(character if character.isalnum() or character in " -_" else "_" for character in self.profile.name)
        path = filedialog.asksaveasfilename(
            parent=self, title="Export Launchpad profile",
            defaultextension=".lpm", initialfile=f"{suggested}.lpm",
            filetypes=[("Launchpad profile", "*.lpm")],
        )
        if not path: return
        try:
            export_profile(self.profile, Path(path))
            messagebox.showinfo("Profile exported", f"‘{self.profile.name}’ is ready to share.")
        except Exception as exc:
            messagebox.showerror("Could not export profile", str(exc))

    def _import_profile(self):
        path = filedialog.askopenfilename(
            parent=self, title="Import Launchpad profile",
            filetypes=[("Launchpad profile", "*.lpm"), ("All files", "*.*")],
        )
        if not path: return
        try:
            profile = import_profile(Path(path), APP_DIR / "icons")
            profile.name = unique_profile_name(profile.name, [item.name for item in self.store.profiles])
            self.store.profiles.append(profile)
            self.store.save(); self._activate_profile(profile.name)
            messagebox.showinfo("Profile imported", f"Imported as ‘{profile.name}’. All mappings and icons are ready.")
        except Exception as exc:
            messagebox.showerror("Could not import profile", str(exc))

    def _save_profile_settings(self):
        self.profile.executable = os.path.basename(self.exe_var.get().strip())
        self.store.auto_switch = self.auto_var.get(); self.store.save()

    def _poll_foreground(self):
        if self.store.auto_switch and not self.recording and not self.colour_assignment and not self.icon_assignment:
            matched = self.store.match_executable(foreground_executable())
            if matched and matched is not self.profile: self._activate_profile(matched.name)
        self.after(800, self._poll_foreground)

    def _refresh_all(self):
        names = [p.name for p in self.store.profiles]; self.profile_combo["values"] = names; self.profile_var.set(self.profile.name)
        self.exe_var.set(self.profile.executable); self.auto_var.set(self.store.auto_switch); self._refresh_editor(); self._refresh_pads(); self._update_leds()

    def _refresh_editor(self):
        kind, number = self.selected.split(":"); self.control_title.configure(text=f"{kind.upper()}  {number}")
        binding = self.profile.bindings.get(self.selected)
        self.shortcut.configure(text=shortcut_text(binding.keys) if binding and binding.keys else "Not assigned")
        self.label_var.set(binding.label if binding else "")
        if not self.colour_assignment:
            self.brush_unpressed = binding.color if binding else 21
            self.brush_pressed = binding.pressed_color if binding else 45
        if not self.icon_assignment:
            self.icon_brush = binding.icon if binding else ""
            self._refresh_icon_caption()
        self._refresh_palette_display()

    def _refresh_palette_display(self):
        colour_names = {number: name for name, number, _rgb in PALETTE}
        self.unpressed_colour_caption.configure(text=f"Unpressed: {colour_names.get(self.brush_unpressed, self.brush_unpressed)}")
        self.pressed_colour_caption.configure(text=f"Pressed: {colour_names.get(self.brush_pressed, self.brush_pressed)}")
        for pressed, chosen in ((False, self.brush_unpressed), (True, self.brush_pressed)):
            for number, swatch in self.colour_swatches[pressed].items():
                swatch.configure(relief="solid" if number == chosen else "flat",
                                 bd=2 if number == chosen else 0, highlightthickness=0)

    def _refresh_pads(self):
        for cid, widget in self.pad_widgets.items():
            binding = self.profile.bindings.get(cid); selected = cid == self.selected
            rgb = PALETTE_RGB.get(binding.color, PAD_ON) if binding else PAD_OFF
            icon = self._icon_image(binding.icon, self.pad_sizes[cid]) if binding and binding.icon else None
            if icon:
                self.pad_frames[cid].configure(bg=rgb)
                widget.configure(image=icon, text="", bg=CARD, activebackground=CARD,
                                 highlightthickness=0, relief="flat", bd=0,
                                 width=24 if self.pad_sizes[cid] else 38,
                                 height=18 if self.pad_sizes[cid] else 30)
            else:
                fill = PAD_SELECTED if selected else rgb
                self.pad_frames[cid].configure(bg=fill)
                widget.configure(image="", bg=fill,
                                 activebackground=PAD_SELECTED, highlightthickness=0,
                                 relief="flat", bd=0,
                                 width=3 if self.pad_sizes[cid] else 5,
                                 height=1 if self.pad_sizes[cid] else 2,
                                 text=(binding.label[:6] if binding and binding.label else ""), fg=TEXT)

    def _icon_image(self, path, small):
        if not path or not os.path.isfile(path): return None
        key = (path, small)
        if key in self.icon_images: return self.icon_images[key]
        try:
            size = (22, 16) if small else (36, 28)
            if Image and ImageTk:
                with Image.open(path) as source:
                    icon = ImageOps.contain(source.convert("RGBA"), size, Image.Resampling.LANCZOS)
                    photo = ImageTk.PhotoImage(icon)
            else:
                photo = tk.PhotoImage(file=path)
            self.icon_images[key] = photo
            return photo
        except Exception:
            return None

    def _paint_pad(self, cid, pressed):
        binding = self.profile.bindings.get(cid)
        if not binding: return
        colour = binding.pressed_color if pressed else binding.color
        rgb = PALETTE_RGB.get(colour, PAD_ON)
        if binding.icon and self._icon_image(binding.icon, self.pad_sizes[cid]):
            self.pad_frames[cid].configure(bg=rgb)
        else:
            self.pad_frames[cid].configure(bg=rgb)
            self.pad_widgets[cid].configure(bg=rgb)

    def _update_leds(self):
        if not self.midi or not self.midi.output: return
        for cid in self.pad_widgets:
            kind, number = cid.split(":"); binding = self.profile.bindings.get(cid)
            self.midi.set_led(kind, int(number), binding.color if binding else 0)

    def _connection_animation(self):
        if not self.midi or not self.midi.output: return
        self.animation_generation += 1
        generation = self.animation_generation
        for cid in self.pad_widgets:
            kind, number = cid.split(":"); self.midi.set_led(kind, int(number), 0)
        colours = (5, 9, 13, 17, 21, 29, 37, 45, 49)

        def finish():
            if generation == self.animation_generation and self.midi.output: self._update_leds()

        def sweep(column=0):
            if generation != self.animation_generation or not self.midi.output: return
            colour = colours[column]
            if column < 8:
                self.midi.set_led("cc", 91 + column, colour)
                for row in range(1, 9): self.midi.set_led("note", row * 10 + column + 1, colour)
            else:
                for row in range(1, 9): self.midi.set_led("note", row * 10 + 9, colour)
            if column < 8: self.after(75, lambda: sweep(column + 1))
            else: self.after(350, finish)

        sweep()

    def _close(self):
        self.animation_generation += 1
        self.store.save()
        if self.midi: self.midi.disconnect()
        self.destroy()


if __name__ == "__main__":
    MapperApp().mainloop()
