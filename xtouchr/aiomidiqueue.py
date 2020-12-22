import asyncio as aio
import mido
from janus import Queue

class AioMidiQueue:
    def __init__(self, in_port: mido.ports.BaseInput):
        self._in_port = in_port
        self._in_port.callback = self._new_message
        self._queue: Queue = Queue(256)  # We init this in launch command

    def _new_message(self, msg: mido.Message):
        self._queue.sync_q.put(msg)

    async def get(self) -> mido.Message:
        return await self._queue.async_q.get()

    def __aiter__(self):
        return self

    async def __anext__(self) -> mido.Message:
        return await self.get()