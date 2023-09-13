# dfp_player.py
""" Control DFPlayer Mini over UART """

import uasyncio as asyncio
from data_link import DataLink
from dfp_mini import DfpMiniCh
from pl_player import PlPlayer
from dfp_support import DfpButtons
from uqueue import Buffer


async def main():
    """ test playlist player controller
        - playlist interface indexes tracks from 1
    """
    print('In main()')

    async def keep_alive():
        """ keep-alive loop """
        while True:
            await asyncio.sleep_ms(1_000)

    def build_player(uart_params_, btn_pins_):
        """ build player from components """
        data_link = DataLink(*uart_params_, Buffer(), Buffer())
        cmd_handler = DfpMiniCh(data_link)
        pl_player = PlPlayer(cmd_handler)
        btns = DfpButtons(*btn_pins_)
        btns.next_track = pl_player.next_pl_track
        btns.dec_vol = pl_player.dec_vol
        btns.inc_vol = pl_player.inc_vol
        return pl_player, btns

    # pin_tx, pin_rx, baud_rate, ba_size)
    uart_params = (0, 1, 9600, 10)
    # play_pin, v_dec_pin, v_inc_pin
    btn_pins = (20, 21, 22)

    player, buttons = build_player(uart_params, btn_pins)
    asyncio.create_task(player.led.blink(5))
    buttons.poll_buttons()
    await asyncio.sleep_ms(2_000)  # allow for power-up
    await player.startup()
    print(f"{player.config['name']}: configuration file loaded")
    print(f'Number of SD tracks: {player.track_count}')
    player.build_playlist(shuffled=True)
    # play track 1 as test
    await player.play_pl_track(1)
    player.print_player_settings()
    await keep_alive()

if __name__ == '__main__':
    try:
        asyncio.run(main())
    finally:
        asyncio.new_event_loop()  # clear retained state
        print('execution complete')
