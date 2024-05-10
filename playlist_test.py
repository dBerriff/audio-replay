# df_player.py
""" Control DFPlayer Mini over UART """

import asyncio
from dfp_support import LedFlash
from data_link import DataLink
from dfp_mini import DfpMini
from playlist_player import PlPlayer
from uqueue import Buffer


async def main():
    """ test playlist player controller """

    async def keep_alive():
        """ keep-alive loop """
        for _ in range(60):
            await asyncio.sleep_ms(1_000)

    def build_player(tx_p, rx_p, btn_pins_):
        """ build player from components """
        data_link = DataLink(tx_p, rx_p, 9600, 10, Buffer(), Buffer())
        cmd_handler = DfpMini(tx_p, rx_p)
        return PlPlayer(cmd_handler, btn_pins_)

    # pins
    # UART
    tx_pin = 16
    rx_pin = 17
    # ADC
    adc_pin = 26
    led_pin = 'LED'
    
    adc = LedFlash(adc_pin, led_pin)
    asyncio.create_task(adc.poll_input())

    # play_pin, v_dec_pin, v_inc_pin
    btn_pins = (20, 21, 22)

    player = build_player(tx_pin, rx_pin, btn_pins)
    print(f'Player name: {player.name}')
    await player.reset()
    player.build_playlist(shuffled=False)
    print(f'Config: {player.config}')
    player.build_playlist()
    await player.play_playlist()


if __name__ == '__main__':
    try:
        asyncio.run(main())
    finally:
        asyncio.new_event_loop()  # clear retained state
        print('execution complete')
