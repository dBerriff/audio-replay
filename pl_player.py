# dfp_player.py
""" Control DFPlayer Mini over UART """

import uasyncio as asyncio
from data_link import DataLink
from dfp_mini import CommandHandler
from dfp_player import PlPlayer
from dfp_support import Led, DfpButtons
from queue import Buffer


async def main():
    """ test playlist player controller
        - playlist interface indexes tracks from 1
    """

    async def loop():
        """ do nothing loop """
        while True:
            await asyncio.sleep_ms(1000)

    onboard = Led('LED')
    uart_params = (0, 1, 9600, 10)
    bytearray_size = 10
    btn_pins = (20, 21, 22)
    rx_queue = Buffer()
    
    asyncio.create_task(onboard.blink(10))
    # allow for player power-up
    await asyncio.sleep_ms(1000)

    # instantiate rx queue and app layers
    data_link = DataLink(*uart_params, rx_queue)
    cmd_handler = CommandHandler(data_link)
    player = PlPlayer(cmd_handler)

    buttons = DfpButtons(*btn_pins)
    buttons.next_track = player.next_track
    buttons.dec_vol = player.dec_vol
    buttons.inc_vol = player.inc_vol
    buttons.poll_buttons()

    cmd, param = await player.startup()
    print(f'Return from initialise: cmd: {cmd:0x}, param: {param:0x}')
    print(f"{player.config['name']}: configuration file loaded")
    print(f'Number of SD tracks: {player.track_count}')
    await player.qry_vol()
    await player.qry_eq()

    player.build_playlist(shuffled=False)
    await player.play_playlist()

if __name__ == '__main__':
    try:
        asyncio.run(main())
    finally:
        asyncio.new_event_loop()  # clear retained state
        print('execution complete')
