import xtouchr.midicontrols as mc
import xtouchr.osccontrols as osc
from xtouchr.controls import Control
import abc
import typing as ty
from enum import Enum
import asyncio as aio


class DAWToggleSetOnly(Control):
    def __init__(self, button: mc.LEDButton, osc: osc.OSCToggleSetOnly):
        super().__init__()
        self._button = button
        self._osc = osc
        self._button.register(self.midi_callback)
        self._osc.register(self.osc_callback) 

    def midi_callback(self, data: ty.Dict):
        if ('pressed' in data and data['pressed']):
            self._osc.on = True

        self._button.led = self._button.LED.ON if self._osc.on else self._button.LED.OFF

    def osc_callback(self, data: ty.Dict):
        if ('on' in data):
            self._button.led = self._button.LED.ON if data['on'] else self._button.LED.OFF

class DAWMainFader(Control):
    def __init__(self, fader: mc.Fader, osc: osc.OSCFader):
        super().__init__()
        self.fader = fader
        self.osc = osc
        self.fader.register(self._midi_cb)

    def _midi_cb(self, _notes):
        self.osc.value = self.fader.value / 127.0

class ArdourStripFaderControl(Control):
    RECENABLE_TIME = 1.0
    LONGPRESS_TIME = 0.5

    class Property(Enum):
        FADER = 0
        STEREO_POS = 1
        TRIM = 2

    def __init__(self,
                fader: mc.LEDFader, 
                fader_button: mc.Button,
                osc_fader: osc.OSCFader,
                osc_trim: osc.OSCFader,
                osc_stereo_pos: osc.OSCFader,
                osc_recenable: osc.OSCToggle):
        super().__init__()
        self.fader = fader
        self.fader_button = fader_button
        self.osc_fader = osc_fader
        self.osc_trim = osc_trim
        self.osc_stereo_pos = osc_stereo_pos
        self.osc_recenable = osc_recenable
        # My own state
        self._property = self.Property.FADER    # Which strip control is edited/shown on the fader
        self.fader.mode = self.fader.Mode.FAN
        self._rec_longpress_timer = None
        self._recenable_reshow_timer = None
        self._register_callbacks()

    def _register_callbacks(self):
        self.fader.register(self.midi_fader_cb)
        self.fader_button.register(self.midi_fader_button_cb)
        self.osc_fader.register(self.osc_fader_cb)
        self.osc_trim.register(self.osc_trim_cb)
        self.osc_stereo_pos.register(self.osc_stereo_pos_cb)
        self.osc_recenable.register(self.osc_recenable_cb)
    
    def midi_fader_cb(self, notes: dict):
        if ('value' in notes):
            if self._property == self.Property.FADER:
                self.osc_fader.value = notes['value'] / 127.0
                self._possibly_recenable_timer()
            elif self._property == self.Property.STEREO_POS:
                self.osc_stereo_pos.value = 1.0 - (notes['value'] / 127.0)
                self._possibly_recenable_timer()
            elif self._property == self.Property.TRIM:
                self.osc_trim.value = notes['value'] * 40.0 / 127.0 - 20.0
                self._possibly_recenable_timer()
    
    def midi_fader_button_cb(self, notes: dict):
        if notes['pressed']:
            # Button was just pressed, start longpress timer
            if self._rec_longpress_timer:
                self._rec_longpress_timer.cancel()

            self._rec_longpress_timer = aio.get_running_loop().call_later(self.LONGPRESS_TIME, self._longpress)
        else:
            # Button was released, if longpress timer not expired, we handle it here
            if not self._rec_longpress_timer:
                return
            
            self._rec_longpress_timer.cancel()
            self._rec_longpress_timer = None

            if self._property == self._property.FADER:
                self.fader.mode = self.fader.mode.PAN
                self.fader.value = int(127.9 * (1.0 - self.osc_stereo_pos.value))
                self._property = self._property.STEREO_POS
            elif self._property == self._property.STEREO_POS:
                self.fader.mode = self.fader.mode.TRIM
                self.fader.value = int(127.9 * (self.osc_trim.value + 20.0) / 40.0)
                self._property = self._property.TRIM
            elif self._property == self._property.TRIM:
                self.fader.mode = self.fader.mode.FAN
                self.fader.value = int(127.9 * self.osc_fader.value)
                self._property = self._property.FADER
            self._possibly_recenable_timer()
    
    def osc_fader_cb(self, notes: dict):
        # Are we on the fader?
        if self._property == self.Property.FADER:
            # Pass the value through
            self.fader.value = int(127.9 * notes['value'])
            self._possibly_recenable_timer()

    def osc_trim_cb(self, notes: dict):
        # Are we on the trim?
        if self._property == self.Property.TRIM:
            # Pass the value through
            self.fader.value = int(127.9 * (notes['value'] + 20.0) / 40.0)
            self._possibly_recenable_timer()

    def osc_stereo_pos_cb(self, notes: dict):
        # Are we on stereo pos?
        if self._property == self.Property.STEREO_POS:
            # Pass the value through
            self.fader.value = int(127.9 * (1.0 - notes['value']))
            self._possibly_recenable_timer()

    def osc_recenable_cb(self, notes: dict):
        if notes['on']:
            # Make the fader blink when recenable is on
            self.fader.led = self.fader.LED.BLINKING
        else:
            # Return to last shown thing
            self.fader.led = self.fader.LED.FADER

    def _possibly_recenable_timer(self):
        if self.osc_recenable.on:
            if self._recenable_reshow_timer is not None:
                self._recenable_reshow_timer.cancel()

            self._recenable_reshow_timer = aio.get_running_loop().call_later(self.RECENABLE_TIME, self._set_recenable)

    def _set_recenable(self):
        if self.osc_recenable.on:
            self.fader.led = self.fader.LED.BLINKING
        self._recenable_reshow_timer = None

    def _longpress(self):
        self.osc_recenable.on = not self.osc_recenable.on
        self._rec_longpress_timer = None

    @staticmethod
    def build(mididev: "mididevice.Device", oscdev: "aiosc.OSCProtocol", midi_strip_id: int, osc_strip_id: int) -> "ArdourStripControl":
        fader = mc.LEDFader(mididev, midi_strip_id, midi_strip_id)
        fader_button = mc.Button(mididev, midi_strip_id-1)
        osc_fader = osc.OSCFader(oscdev, '/strip/fader', osc_strip_id)
        osc_trim = osc.OSCFader(oscdev, '/strip/trimdB', osc_strip_id)
        osc_stereo_pos = osc.OSCFader(oscdev, '/strip/pan_stereo_position', osc_strip_id)
        osc_recenable = osc.OSCToggle(oscdev, '/strip/recenable', osc_strip_id)
        return ArdourStripFaderControl(fader, fader_button, osc_fader, osc_trim,
                                osc_stereo_pos, osc_recenable)


class ArdourSoloMuteControl(Control):
    LONGPRESS_TIME = 0.3

    def __init__(self, led_button: mc.LEDButton,
                       osc_mute: osc.OSCToggle,
                       osc_solo: osc.OSCToggle,
                       cancel_all_solos: osc.OSCToggle,
                       osc_group: osc.OSCValue):
        super().__init__()
        self.led_button = led_button
        self.osc_mute = osc_mute
        self.osc_solo = osc_solo
        self.cancel_all_solos = cancel_all_solos
        self.osc_group = osc_group
        # My own state
        self.led_button.led = self.led_button.LED.OFF
        self._longpress_timer = None
        self._register_callbacks()

    def _register_callbacks(self):
        self.led_button.register(self.led_button_cb)
        self.osc_mute.register(self.recalculate)
        self.osc_solo.register(self.recalculate)
        self.osc_group.register(self.recalculate)
        self.cancel_all_solos.register(self.recalculate)

    def led_button_cb(self, notes: dict):
        if 'pressed' in notes:
            if notes['pressed']:
                # Button was just pressed, start longpress timer
                if self._longpress_timer:
                    self._longpress_timer.cancel()

                # Only start timer if not soloing
                self._longpress_timer = aio.get_running_loop().call_later(self.LONGPRESS_TIME, self._longpress)
            else:
                # Button was released, if longpress timer not expired, we handle it here
                if self._longpress_timer:
                    self._longpress_timer.cancel()
                    self._longpress_timer = None

                    # If we were soloing, just disable the solo
                    if self.osc_solo.on:
                        self.osc_solo.on = False
                    else:
                        # Toggle the mute
                        self.osc_mute.on = not self.osc_mute.on

        # In any case, recalculate the state
        self.recalculate()

    def recalculate(self, _notes=None):
        is_soloing = self.osc_solo.on
        is_weak_muted = self.cancel_all_solos.on
        is_strong_muted = self.osc_mute.on
        is_inactive = self.osc_group.value == 'none'

        if is_inactive:
            # There is no track under this strip, always OFF
            self.led_button.led = self.led_button.LED.OFF
        elif is_strong_muted:
            # Strongly muted
            self.led_button.led = self.led_button.LED.OFF
        elif is_soloing:
            # Might be muted due to other solo, but playing since soloing itself
            self.led_button.led = self.led_button.LED.BLINKING
        elif is_weak_muted:
            # Muted due to other tracks soloing
            self.led_button.led = self.led_button.LED.OFF
        else:
            # Happily playing along
            self.led_button.led = self.led_button.LED.ON

    def _longpress(self):
        # Toggle soloing here
        self._longpress_timer = None
        if self.osc_mute.on and not self.osc_solo.on:
            self.osc_solo.on = True
            self.osc_mute.on = False
        elif self.osc_mute.on and self.osc_solo.on:
            self.osc_mute.on = False
        else:
            self.osc_solo.on = not self.osc_solo.on

    @staticmethod
    def build(mididev: "mididevice.Device", oscdev: "aiosc.OSCProtocol", midi_strip_id: int, osc_strip_id: int) -> "ArdourSoloMuteControl":
        led_button = mc.LEDButton(mididev, 7+midi_strip_id, midi_strip_id-1)
        osc_mute = osc.OSCToggle(oscdev, '/strip/mute', osc_strip_id)
        osc_solo = osc.OSCToggle(oscdev, '/strip/solo', osc_strip_id)        
        osc_cancel_all_solos = osc.OSCToggle(oscdev, '/cancel_all_solos')
        osc_group = osc.OSCValue(oscdev, '/strip/group', osc_strip_id)
        return ArdourSoloMuteControl(led_button, osc_mute, osc_solo, osc_cancel_all_solos, osc_group)

class ArdourRecordButton(Control):
    def __init__(self,
                 led_button: mc.LEDButton,
                 osc_rec_enable: osc.OSCToggle,
                 osc_rec_tally: osc.OSCValue,
                 osc_play = osc.OSCValue):
        self.led_button = led_button
        self.osc_rec_enable = osc_rec_enable
        self.osc_rec_tally = osc_rec_tally
        self.osc_play = osc_play
        self._register_callbacks()

    def _register_callbacks(self):
        self.led_button.register(self._midi_cb)
        self.osc_rec_enable.register(self._recalculate)
        self.osc_rec_tally.register(self._recalculate)
        self.osc_play.register(self._recalculate)

    def _midi_cb(self, notes: dict):
        if 'pressed' in notes and notes['pressed']:
            # We actually need to toggle it this time
            self.osc_rec_enable.on = False
            self.osc_rec_enable.on = True
        self._recalculate(None)

    def _recalculate(self, _notes):
        is_record_armed = bool(self.osc_rec_enable.on)
        is_transport_moving = bool(self.osc_play.value)
        is_tally = bool(self.osc_rec_tally.value)
        print(f"recalc, ira: {is_record_armed}, play: {is_transport_moving}, tally: {is_tally}")

        if is_record_armed and is_transport_moving and is_tally:
            self.led_button.led = self.led_button.LED.ON
        elif is_record_armed:
            self.led_button.led = self.led_button.LED.BLINKING
        else:
            self.led_button.led = self.led_button.LED.OFF    

    @staticmethod
    def build(mididev: "mididevice.Device", oscdev: "aiosc.OSCProtocol"):
        led_button = mc.LEDButton(mididev, 23, 15)
        osc_rec_enable = osc.OSCToggle(oscdev, '/rec_enable_toggle')
        osc_rec_tally = osc.OSCValue(oscdev, '/record_tally')
        osc_play = osc.OSCValue(oscdev, '/transport_play')
        return ArdourRecordButton(led_button, osc_rec_enable, osc_rec_tally, osc_play)

class ArdourLoopToggle(Control):
    def __init__(self, led_button: mc.LEDButton, osc_loop: osc.OSCToggle):
        super().__init__()
        self.led_button = led_button
        self.osc_loop = osc_loop
        self.led_button.register(self._midi_cb)
        self.osc_loop.register(self._recalculate)

    def _midi_cb(self, notes: dict):
        if ('pressed' in notes and notes['pressed']):
            self.osc_loop.on = False
            self.osc_loop.on = True
        self._recalculate(None)

    def _recalculate(self, _notes):
        if self.osc_loop.on:
            self.led_button.led = self.led_button.LED.ON
        else:
            self.led_button.led = self.led_button.LED.OFF

class ArdourJogControl(Control):
    INITIAL = 5.0
    INCREMENT = 4.0
    INITIAL_WAIT = 0.4
    INCREMENT_WAIT = 0.1
    def __init__(self, button: mc.Button, osc_jog: osc.OSCAction, forward: bool):
        super().__init__()
        self.button = button
        self.osc_jog = osc_jog
        self.mul = 1.0 if forward else -1.0
        self._timer = None
        self.button.register(self._midi_cb)

    def _midi_cb(self, notes: dict):
        if 'pressed' in notes:
            if notes['pressed']:
                if self._timer is not None:
                    self._timer.cancel()

                self.osc_jog.action(self.INITIAL * self.mul)
                self._timer = aio.get_running_loop().call_later(self.INITIAL_WAIT, self._incremental)
            else:
                if self._timer is not None:
                    self._timer.cancel()
                    self._timer = None

    def _incremental(self):
        self.osc_jog.action(self.INCREMENT * self.mul)
        self._timer = aio.get_running_loop().call_later(self.INCREMENT_WAIT, self._incremental)


class ArdourConnectGuard(Control):
    TIMEOUT = 10.0
    CONN_INTERVAL = 3.0

    def __init__(self, surface: osc.OSCAction, heartbeat: osc.OSCValue):
        self.surface = surface
        self.heartbeat = heartbeat
        self.heartbeat.register(self._heartbeat_cb)
        self._connect()

    def _heartbeat_cb(self, _notes):
        if self.timer is not None:
            self.timer.cancel()
        
        self.timer = aio.get_running_loop().call_later(self.CONN_INTERVAL, self._connect)

    def _connect(self):
        self.surface.action()
        self.timer = aio.get_running_loop().call_later(self.CONN_INTERVAL, self._connect)