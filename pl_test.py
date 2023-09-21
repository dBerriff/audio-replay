# dfp_player.py
""" Control DFPlayer Mini over UART """

import uasyncio as asyncio
from data_link import DataLink
from dfp_mini import DfpMiniControl
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

    def build_player(tx_p, rx_p):
        """ build player from components """
        data_link = DataLink(tx_p, rx_p, 9600, 10, Buffer(), Buffer())
        cmd_handler = DfpMiniControl(data_link)
        return PlPlayer(cmd_handler)

    def build_buttons(pl_player_, btn_pins_):
        buttons_ = DfpButtons(*btn_pins_)
        buttons_.next_track = pl_player_.next_pl_track
        buttons_.dec_vol = pl_player_.dec_vol
        buttons_.inc_vol = pl_player_.inc_vol
        return buttons_


    # play_pin, v_dec_pin, v_inc_pin
    btn_pins = (20, 21, 22)

    player = build_player(0, 1)
    buttons = build_buttons(player, btn_pins)
    buttons.poll_buttons()
    await asyncio.sleep_ms(2_000)  # allow for power-up
    await player.startup()
    print(f"{player.config['name']} configuration file loaded")
    print(f'Number of SD tracks: {player.ch_track_count}')
    player.build_playlist(shuffled=True)
    # play track 1 as test
    await player.play_pl_track(1)
    # player.print_player_settings()
    await keep_alive()

if __name__ == '__main__':
    try:
        asyncio.run(main())
    finally:
        asyncio.new_event_loop()  # clear retained state
        print('execution complete')
