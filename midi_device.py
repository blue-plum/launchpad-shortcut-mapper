from __future__ import annotations

import rtmidi


PROGRAMMER_MODE = [0xF0, 0x00, 0x20, 0x29, 0x02, 0x0D, 0x0E, 0x01, 0xF7]
LIVE_MODE = [0xF0, 0x00, 0x20, 0x29, 0x02, 0x0D, 0x0E, 0x00, 0xF7]


class LaunchpadMidi:
    def __init__(self, callback):
        self.callback = callback
        self.input = None
        self.output = None

    @staticmethod
    def ports():
        midi_in, midi_out = rtmidi.MidiIn(), rtmidi.MidiOut()
        return midi_in.get_ports(), midi_out.get_ports()

    def connect(self, input_name: str, output_name: str):
        self.disconnect()
        ins, outs = self.ports()
        self.input, self.output = rtmidi.MidiIn(), rtmidi.MidiOut()
        self.input.open_port(ins.index(input_name))
        self.output.open_port(outs.index(output_name))
        self.input.ignore_types(sysex=True, timing=True, active_sense=True)
        self.input.set_callback(self._message)
        self.output.send_message(PROGRAMMER_MODE)

    def disconnect(self):
        if self.output:
            try:
                self.output.send_message(LIVE_MODE)
            except Exception:
                pass
        for port in (self.input, self.output):
            if port:
                try:
                    port.close_port()
                except Exception:
                    pass
        self.input = self.output = None

    def _message(self, event, _data=None):
        message, _delta = event
        if len(message) < 3:
            return
        status, number, value = message[:3]
        command = status & 0xF0
        if command in (0x80, 0x90):
            self.callback("note", number, command == 0x90 and value > 0)
        elif command == 0xB0:
            self.callback("cc", number, value > 0)

    def set_led(self, kind: str, number: int, color: int):
        if self.output:
            status = 0x90 if kind == "note" else 0xB0
            self.output.send_message([status, number, max(0, min(127, color))])
