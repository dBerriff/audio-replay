# dfp_control.py
""" Control DFPlayer Mini over UART """

import uasyncio as asyncio
from dfp_control import DfPlayer


async def main():
    """ test DFPlayer controller """
    player = DfPlayer(0, 1)
    command_handler = player.c_h
    asyncio.create_task(command_handler.stream_tr.receiver())
    asyncio.create_task(command_handler.consume_rx_data())
    
    await player.reset()
    await player.vol_set(29)
    await player.q_vol()
    for repeat in range(5):
        for index in range(3):
            track = index + 1
            await player.play_trk(track)
            await asyncio.sleep_ms(1000)

    
    

if __name__ == '__main__':
    try:
        asyncio.run(main())
    finally:
        asyncio.new_event_loop()  # clear retained state
        print('test complete')
