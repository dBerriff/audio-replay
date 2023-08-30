# dfp_player.py
""" Control DFPlayer Mini over UART """

import uasyncio as asyncio
from machine import Pin
from dfp_player import DfPlayer
from dfp_mini import CommandHandler


class HwSwitch:
    """
        input pin class for hardware switch or button
        - Pull.UP logic
        - returned states: 0 for off (open), 1 for on (closed)
        - this inverts pull-up logic
    """

    def __init__(self, pin):
        self.pin = pin  # for diagnostics
        self._hw_in = Pin(pin, Pin.IN, Pin.PULL_UP)
        self.is_on = asyncio.Event()
        self.player_ready = asyncio.Event()

    def get_state(self):
        """ check for switch state """
        return 0 if self._hw_in.value() == 1 else 1
    
    async def poll_state(self):
        """ poll 'play' button """
        while True:
            await self.player_ready.wait()
            if self.get_state():
                self.is_on.set()
            await asyncio.sleep_ms(200)
                
        
async def main():
    """ test DFPlayer controller """
    print('Starting...')
    sw = HwSwitch(16)
    ch_tr = CommandHandler()
    player = DfPlayer(ch_tr)
    # tasks to receive and process response words
    asyncio.create_task(ch_tr.stream_tr.receiver())
    asyncio.create_task(ch_tr.consume_rx_data())
    print('Run commands')    
    await player.reset()
    await player.vol_set(15)
    await player.q_vol()
    asyncio.create_task(sw.poll_state())
    while True:
        for index in range(player.track_count):
            sw.player_ready.set()
            await sw.is_on.wait()
            sw.player_ready.clear()
            sw.is_on.clear()
            track = index + 1
            await player.play_track(track)
            await asyncio.sleep_ms(1000)


if __name__ == '__main__':
    try:
        asyncio.run(main())
    finally:
        asyncio.new_event_loop()  # clear retained state
        print('test complete')
