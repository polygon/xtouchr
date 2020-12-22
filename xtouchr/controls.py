import abc
import typing as ty
import asyncio as aio

CT = ty.TypeVar('CT')

class MaybeNotify:
    def __init__(self, ctrl: "Control"):
        self._ctrl = ctrl
        self._notes = None

    def __enter__(self):
        self._notes = dict()
        return self

    def assign(self, old: CT, new: CT, oid: ty.Hashable) -> CT:
        if (old != new):
            self._notes[oid] = new

        return new

    def __exit__(self, *args):
        if self._notes:
            self._ctrl.notify(self._notes)


class Control(abc.ABC):
    def __init__(self):
        self.listeners = list()

    def register(self, listener: ty.Callable):
        self.listeners.append(listener)

    def notify(self, *args):
        loop = aio.get_running_loop()
        for l in self.listeners:
            l(*args)
            
    def maybe_notify(self) -> MaybeNotify:
        """
        Since we are only supposed to update state when it is actuallly changed,
        this function will take this task. If you want to set the state to a new value
        but don't want to check if it has changed, just do it as follows:

        with ctrl.maybe_notify() as m:
            self._state = m.assign(self._state, new_state, 'statename')
            # Possibly more statements here

        This will in any case set self._state to new_state. In the background, it will
        compare the states and add changed states together with their ID to a notification
        dictionary. After exiting the with-scope, a change notification is triggered only
        if something has actually changed and then only those values that did actually change.
        """
        return MaybeNotify(self)