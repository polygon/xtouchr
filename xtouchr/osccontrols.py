from xtouchr.controls import Control
import aiosc
import time

class ReplyFilter:
    def __init__(self, maxage = 1.0):
        self._replies = list()
        self._maxage = maxage

    def _check_eq(self, a, b):
        return a == b

    def add_sent(self, val):
        self._replies.append((time.time(), val))

    def _filter_old(self):
        now = time.time()
        self._replies = list(filter(lambda a: now-a[0] < self._maxage, self._replies))

    def is_reply(self, val) -> bool:
        self._filter_old()
        reply = next(filter(lambda a: self._check_eq(a[1][1], val), enumerate(self._replies)), None)
        if reply is not None:
            del self._replies[reply[0]]
            print("Reply found!")
            return True

        print("No reply found!")
        return False

class ReplyFilterFloat(ReplyFilter):
    def __init__(self, maxage = 1.0, limit = 0.0001):
        super().__init__(maxage)
        self._limit = limit

    def _check_eq(self, a, b):
        return (abs(a-b) < self._limit)

class OSCToggleBase(Control):
    def __init__(self, osc: aiosc.OSCProtocol, path: str, *args):
        super().__init__()
        self.osc = osc
        self.path = path
        self.checked_args = args
        self.osc.add_handler(self.path, self.osc_callback)
        self._on = False    # Tracks state of control within OSC endpoint

    def osc_callback(self, _addr, _path, *args):
        incoming_args = args[:-1]
        new_on = bool(args[-1])
        if len(incoming_args) != len(self.checked_args):
            # Message is not for us
            return

        if any(ca != ia for ca, ia in zip(self.checked_args, incoming_args)):
            # Message is not for us (e.g. other fader ID)
            return

        with self.maybe_notify() as m:
            self._on = m.assign(self._on, new_on, 'on')

class OSCToggle(OSCToggleBase):
    @property
    def on(self) -> bool:
        return self._on
        
    @on.setter
    def on(self, val: bool):
        if (self._on != val):
            with self.maybe_notify() as m:
                self._on = m.assign(self._on, val, 'on')
            self._update_osc()

    def _update_osc(self):
        self.osc.send(self.path, *self.checked_args, float(self._on))

class OSCToggleSetOnly(OSCToggleBase):
    """
    Used for OSC properties that can go on and off, but can only be
    turned on using the control
    """
    @property
    def on(self) -> bool:
        return self._on
        
    @on.setter
    def on(self, val: bool):
        if (val == False):
            print(f"Tried to set False on Set-Only switch: {self.path}")

        if (self._on != val):
            with self.maybe_notify() as m:
                self._on = m.assign(self._on, val, 'on')
            self._update_osc()

    def _update_osc(self):
        if (self._on):
            self.osc.send(self.path, *self.checked_args, float(self._on))

class OSCFader(Control):
    """
    Used to read and write float values
    """
    def __init__(self, osc: aiosc.OSCProtocol, path: str, *args):
        super().__init__()
        self.osc = osc
        self.path = path
        self.checked_args = args
        self.osc.add_handler(self.path, self.osc_callback)
        self.filter = ReplyFilterFloat()
        self._value = 0.0    # Tracks fader value within OSC endpoint
        self._wait_ack_t = 0.0          # Time when we started waiting for ACKs
        self._wait_ack_val = 0.0        # Value that we wait for to be acknowledged
        self._wait_ack_more = False     # Whether there is more after this ack

    def osc_callback(self, _addr, _path, *args):
        incoming_args = args[:-1]
        new_val = float(args[-1])
        if len(incoming_args) != len(self.checked_args):
            # Message is not for us
            return

        if any(ca != ia for ca, ia in zip(self.checked_args, incoming_args)):
            # Message is not for us (e.g. other fader ID)
            return

        if self.filter.is_reply(new_val) or True:
            with self.maybe_notify() as m:
                self._value = m.assign(self._value, new_val, 'value')            
            
    @property
    def value(self) -> float:
        return self._value

    @value.setter
    def value(self, val: float):
        if (self._value != val):
            with self.maybe_notify() as m:
                self._value = m.assign(self._value, val, 'value')
            self._update_osc()

    def _update_osc(self):
        self.filter.add_sent(self._value)
        self.osc.send(self.path, *self.checked_args, float(self._value))

class OSCValue(Control):
    def __init__(self, osc: aiosc.OSCProtocol, path: str, *args, initial=None):
        super().__init__()
        self.osc = osc
        self.path = path
        self.checked_args = args
        self.osc.add_handler(self.path, self.osc_callback)
        self._value = initial

    def osc_callback(self, _addr, _path, *args):
        incoming_args = args[:-1]
        new_value = args[-1]
        if len(incoming_args) != len(self.checked_args):
            # Message is not for us
            return

        if any(ca != ia for ca, ia in zip(self.checked_args, incoming_args)):
            # Message is not for us (e.g. other fader ID)
            return

        with self.maybe_notify() as m:
            self._value = m.assign(self._value, new_value, 'on')    

    @property
    def value(self):
        return self._value

class OSCAction(Control):
    def __init__(self, osc: aiosc.OSCProtocol, path: str, *args):
        super().__init__()
        self.osc = osc
        self.path = path
        self.args = args

    def action(self, *args):
        self.osc.send(self.path, *self.args, *args)