import mido
import typing as ty
import asyncio as aio
import abc
from enum import Enum
import mido
from xtouchr.controls import Control


class LEDButton(Control):
    class LED(Enum):
        OFF = 0
        ON = 1
        BLINKING = 2

    def __init__(self, device: "MidiDevice", note: int, glbl_note: int, channel: int = 10, glbl_channel: int = 0):
        super().__init__()
        self.device = device
        self.note = note
        self.glbl_note = glbl_note
        self.channel = channel
        self.glbl_channel = glbl_channel
        self.device.register_note_callback(self.channel, self.note, self.midi_callback)
        self._led = self.LED.OFF     # Tracks LED state
        self._pressed = False        # Tracks button state
        self.update_midi_device()

    async def midi_callback(self, pressed: bool, velocity: int):
        with self.maybe_notify() as m:
            self._pressed = m.assign(self._pressed, pressed, 'pressed')

            # Device will always turn LED on when button is pressed and off when not
            new_led = self.LED.ON if pressed else self.LED.OFF
            self._led = m.assign(self._led, new_led, 'led')

    @property
    def pressed(self) -> bool:
        return self._pressed

    @property
    def led(self) -> "LEDButton.LED":
        return self._led

    @led.setter
    def led(self, val: "LEDButton.LED"):
        with self.maybe_notify() as m:
            # We still check for change here so we don't sent the MIDI message
            # for unchanged state
            if (self._led != val):
                self._led = m.assign(self._led, val, 'led')
                self.update_midi_device()

    def update_midi_device(self):
        self.device.send(mido.Message('note_on', channel=self.glbl_channel, note=self.glbl_note, velocity=self._led.value))

class LEDFader(Control):
    class Mode(Enum):
        PAN = 1
        FAN = 2
        SPREAD = 3
        TRIM = 4

    class LED(Enum):
        OFF = 0         # All fader LEDs are off
        ON = 27         # All fader LEDs are on
        BLINKING = 28   # All fader LEDs are blinking
        FADER = 255     # Indicating that the fader position is shown

    def __init__(self, device: "MidiDevice", cc: int, glbl_cc: int, channel: int = 10, glbl_channel: int = 0):
        super().__init__()
        self.device = device
        self.cc = cc
        self.glbl_cc = glbl_cc
        self.channel = channel
        self.glbl_channel = glbl_channel
        self.device.register_cc_callback(self.channel, self.cc, self.midi_callback)
        self._mode = None
        self._led = None
        self._value = None
        self.mode = self.Mode.PAN
        self.led = self.LED.FADER
        self.value = 0

    async def midi_callback(self, value: int):
        with self.maybe_notify() as m:
            self._value = m.assign(self._value, value, 'value')

            # Moving any knob will turn global LED state off and show the fader value
            self._led = m.assign(self._led, self.LED.FADER, 'led')

    @property
    def value(self) -> int:
        return self._value
    
    @value.setter
    def value(self, val: int):
        val = int(val)
        if (val < 0) or (val > 127):
            print(f"New fader value {val} not in range [0, 127], ignoring")

        # We don't want to send a MIDI message when not actually changing the value
        if (self._value != val):
            with self.maybe_notify() as m:
                self._value = val
                self._led = m.assign(self._led, self.LED.FADER, 'led')
                self.device.send(mido.Message('control_change', channel=self.channel, control=self.cc, value=self._value))

    @property
    def mode(self) -> "Mode":
        return self._mode

    @mode.setter
    def mode(self, val: "Mode"):
        val = self.Mode(val)
        if (self._mode != val):
            with self.maybe_notify() as m:
                self._mode = m.assign(self._mode, val, 'mode')
                self._led = m.assign(self._led, self.LED.FADER, 'led')
                self.device.send(mido.Message('control_change', channel=self.glbl_channel, control=self.glbl_cc, value=self._mode.value))

    @property
    def led(self) -> "LED":
        return self._led
    
    @led.setter
    def led(self, val: "LED"):
        val = self.LED(val)
        if (self._led != val):
            with self.maybe_notify() as m:
                self._led = m.assign(self._led, val, 'led')
            if self._led == self.LED.FADER:
                # Set fader mode to return showing the fader value
                self.device.send(mido.Message('control_change', channel=self.glbl_channel, control=self.glbl_cc, value=self._mode.value))
            else:
                self.device.send(mido.Message('control_change', channel=self.glbl_channel, control=self.glbl_cc+8, value=self._led.value))


class Button(Control):
    def __init__(self, device: "MidiDevice", note: int, channel: int = 10):
        super().__init__()
        self.device = device
        self.note = note
        self.channel = channel
        self.device.register_note_callback(self.channel, self.note, self.midi_callback)
        self._pressed = False        # Tracks button state

    async def midi_callback(self, pressed: bool, velocity: int):
        with self.maybe_notify() as m:
            self._pressed = m.assign(self._pressed, pressed, 'pressed')

    @property
    def pressed(self) -> bool:
        return self.pressed

class Fader(Control):
    def __init__(self, device: "MidiDevice", cc: int, channel: int = 10):
        super().__init__()
        self.device = device
        self.cc = cc
        self.channel = channel
        self.device.register_cc_callback(self.channel, self.cc, self.midi_callback)
        self._value = 0

    async def midi_callback(self, value: int):
        with self.maybe_notify() as m:
            self._value = m.assign(self._value, value, 'value')

    @property
    def value(self) -> int:
        return self._value