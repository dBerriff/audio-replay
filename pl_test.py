# df_player.py
""" Control DFPlayer Mini over UART """

import uasyncio as asyncio
from dfp_support import LedFlash
from data_link import DataLink
from dfp_mini import DfpMini
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
        cmd_handler = DfpMini(data_link)
        return PlPlayer(cmd_handler)

    # pins
    # UART
    tx_pin = 0
    rx_pin = 1
    # ADC
    adc_pin = 26
    led_pin = 'LED'
    
    adc = LedFlash(adc_pin, led_pin)
    asyncio.create_task(adc.poll_input())
    # play_pin, v_dec_pin, v_inc_pin
    btn_pins = (20, 21, 22)

    player = build_player(tx_pin, rx_pin)
    print(f'Player name: {player.name}')
    await player.reset()
    await player.send_query('vol')

    buttons = DfpButtons(*btn_pins)
    buttons.next_track = player.next_pl_track
    buttons.dec_vol = player.dec_vol
    buttons.inc_vol = player.inc_vol
    buttons.save_config = player.save_config
    buttons.poll_buttons()
    player.build_playlist(shuffled=False)
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
