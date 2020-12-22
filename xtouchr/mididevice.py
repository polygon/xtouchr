import mido
import asyncio as aio
from xtouchr.aiomidiqueue import AioMidiQueue
import typing as ty

class MidiDevice:
    """
    This class manages a MIDI control device, such as the X-Touch mini. It is
    responsible for creating the MIDI in and out ports, dispatching received MIDI
    messages to the correct MidiControl and offer a way to send back messages to
    the device from MidiControls
    """

    def __init__(self, midi_in: mido.ports.BaseInput, midi_out: mido.ports.BaseOutput):
        self.midi_in = midi_in
        self.midi_out = midi_out
        self.queue_in = AioMidiQueue(self.midi_in)
        self.note_callbacks = {}
        self.cc_callbacks = {}

    def register_note_callback(self, channel: int, note: int, callback: ty.Coroutine):
        key = (channel, note)
        if key not in self.note_callbacks:
            self.note_callbacks[key] = [callback]
        else:
            self.note_callbacks[key].append(callback)

    def register_cc_callback(self, channel: int, cc: int, callback: ty.Coroutine):
        key = (channel, cc)
        if key not in self.cc_callbacks:
            self.cc_callbacks[key] = [callback]
        else:
            self.cc_callbacks[key].append(callback)

    async def start(self):
        while True:
            async for msg in self.queue_in:
                if msg.type in ('note_on', 'note_off'):
                    self._deploy_note(msg)
                elif msg.type == 'control_change':
                    self._deploy_cc(msg)

    def _deploy_note(self, msg: mido.Message):
        key = (msg.channel, msg.note)
        on = (msg.type == 'note_on')
        if key in self.note_callbacks:
            for cb in self.note_callbacks[key]:
                aio.get_event_loop().create_task(cb(on, msg.velocity))

    def _deploy_cc(self, msg: mido.Message):
        key = (msg.channel, msg.control)
        if key in self.cc_callbacks:
            for cb in self.cc_callbacks[key]:
                aio.get_event_loop().create_task(cb(msg.value))

    def send(self, msg: mido.Message):
        self.midi_out.send(msg)