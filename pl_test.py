# dfp_player.py
""" Control DFPlayer Mini over UART """

import uasyncio as asyncio
from data_link import DataLink
from dfp_mini import CommandHandler
from pl_player import PlPlayer
from dfp_support import DfpButtons
from queue import Buffer


async def main():
    """ test playlist player controller
        - playlist interface indexes tracks from 1
    """

    async def loop():
        """ keep-alive loop """
        while True:
            await asyncio.sleep_ms(5000)
            player.print_player_settings()

    def build_player(uart_params_, btn_pins_):
        """ build player from components """
        data_link = DataLink(*uart_params_, Buffer(), Buffer())
        cmd_handler = CommandHandler(data_link)
        player_ = PlPlayer(cmd_handler)
        buttons_ = DfpButtons(*btn_pins_)
        buttons_.next_track = player_.next_pl_track
        buttons_.dec_vol = player_.dec_vol
        buttons_.inc_vol = player_.inc_vol
        return player_, buttons_

    # pin_tx, pin_rx, baud_rate, ba_size)
    uart_params = (0, 1, 9600, 10)
    # play_pin, v_dec_pin, v_inc_pin
    btn_pins = (20, 21, 22)

    player, buttons = build_player(uart_params, btn_pins)
    asyncio.create_task(player.led.blink(10))
    buttons.poll_buttons()

    player.print_player_settings()
    await asyncio.sleep_ms(1000)  # allow power-up
    await player.startup()
    print(f"{player.config['name']}: configuration file loaded")
    print(f'Number of SD tracks: {player.track_count}')
    player.print_player_settings()

    player.build_playlist(shuffled=False)
    # play track 1 as test
    await player.play_pl_track(1)
    await loop()

if __name__ == '__main__':
    try:
        asyncio.run(main())
    finally:
        asyncio.new_event_loop()  # clear retained state
        print('execution complete')
