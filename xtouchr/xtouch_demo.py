import mido
from time import sleep
from xtouchr.mididevice import MidiDevice
import asyncio as aio
import os
import typing as ty
import xtouchr.midicontrols as mc
import xtouchr.dawcontrols as dc
import xtouchr.osccontrols as oc
import aiosc

class Server(aiosc.OSCProtocol):
    def __init__(self):
        super().__init__(handlers = {'//*': self.echo})

    def echo(self, addr, path, *args):
        #pass
        print("incoming message from {}: {} {}".format(addr, path, args))        

async def main():
    await aio.sleep(100.0)

def get_xtouch_port_in_name() -> ty.Optional[str]:
    for name in mido.get_input_names():
        if "x-touch mini" in name.lower():
            return name
    return None

def get_xtouch_port_out_name() -> ty.Optional[str]:
    for name in mido.get_output_names():
        if "x-touch mini" in name.lower():
            return name
    return None

def build_midi_ports() -> (mido.ports.BaseInput, mido.ports.BaseOutput):
    mido.set_backend('mido.backends.rtmidi/UNIX_JACK')
    name_in = get_xtouch_port_in_name()
    if name_in is not None:
        pin = mido.open_input(name_in)
    else:
        pin = mido.open_input('xtouch-in', virtual=True, client_name='xtouchr')

    name_out = get_xtouch_port_out_name()
    if name_out is not None:
        pout = mido.open_output(name_out)
    else:
        pout = mido.open_output('xtouch-out', virtual=True, client_name='xtouchr')

    return pin, pout

async def main():
    midi_in, midi_out = build_midi_ports()
    transport, proto = await aio.get_running_loop().create_datagram_endpoint(Server, local_addr=('*', 9000), remote_addr=('127.0.0.1', 3819))
    xtouch = MidiDevice(midi_in, midi_out)
    play_button = mc.LEDButton(xtouch, 22, 14)
    stop_button = mc.LEDButton(xtouch, 21, 13)
    play_osc = oc.OSCToggleSetOnly(proto, '/transport_play')
    stop_osc = oc.OSCToggleSetOnly(proto, '/transport_stop')
    play_ctl = dc.DAWToggleSetOnly(play_button, play_osc)
    stop_ctl = dc.DAWToggleSetOnly(stop_button, stop_osc)
    faders = [dc.ArdourStripFaderControl.build(xtouch, proto, i, i) for i in range(1, 9)]
    solos = [dc.ArdourSoloMuteControl.build(xtouch, proto, i, i) for i in range(1, 9)]
    rec = dc.ArdourRecordButton.build(xtouch, proto)
    loop = dc.ArdourLoopToggle(mc.LEDButton(xtouch, 20, 12), oc.OSCToggle(proto, '/loop_toggle'))
    fwd = dc.ArdourJogControl(mc.Button(xtouch, 19), oc.OSCAction(proto, '/jog'), True)
    rew = dc.ArdourJogControl(mc.Button(xtouch, 18), oc.OSCAction(proto, '/jog'), False)
    master = dc.DAWMainFader(mc.Fader(xtouch, 9), oc.OSCFader(proto, '/master/fader'))
    conn_action = oc.OSCAction(proto, '/set_surface', 8, 31, 27, 1, 0, 0, 9000)
    guard = dc.ArdourConnectGuard(conn_action, oc.OSCValue(proto, '/heartbeat'))
    aio.get_running_loop().create_task(xtouch.start())
    while True:
        await aio.sleep(10.0)

if __name__ == '__main__':
    aio.get_event_loop().run_until_complete(main())