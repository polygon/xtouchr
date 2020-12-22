import asyncio as aio
import aiosc
from xtouchr.osccontrols import OSCToggleSetOnly

class Server(aiosc.OSCProtocol):
    def __init__(self):
        super().__init__(handlers = {'//*': self.echo})

    def echo(self, addr, path, *args):
        pass
        #print("incoming message from {}: {} {}".format(addr, path, args))        

async def main():
    transport, proto = await aio.get_running_loop().create_datagram_endpoint(Server, local_addr=('*', 9000), remote_addr=('127.0.0.1', 3819))
    play = OSCToggleSetOnly(proto, '/transport_play')
    stop = OSCToggleSetOnly(proto, '/transport_stop')
    proto.send('/set_surface', 8, 31, 27, 1, 0, 0, 9000)
    await aio.sleep(100.0)

if __name__ == '__main__':
    aio.get_event_loop().run_until_complete(main())