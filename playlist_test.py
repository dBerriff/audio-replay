# df_player.py
""" Control DFPlayer Mini over UART """

import asyncio
from dfp_support import LedFlash
from dfp_mini import DfpMini
from playlist_player import PlPlayer


async def main():
    """ test playlist player controller """

    # pins
    # UART
    tx_pin = 16
    rx_pin = 17
    # ADC
    adc_pin = 26
    led_pin = 'LED'
    
    adc = LedFlash(adc_pin, led_pin)
    asyncio.create_task(adc.poll_input())

    btn_pins = {"play": 20, "v_dec": 21, "v_inc": 22}
    player = PlPlayer(DfpMini(tx_p, rx_p), btn_pins)
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
