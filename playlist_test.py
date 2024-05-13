# df_player.py
""" Control DFPlayer Mini over UART """

import asyncio
from dfp_mini import DfpMini
from playlist_player import PlPlayer
from dfp_support import Led


async def main():
    """ test playlist player controller """

    # pins
    # UART
    tx_pin = 16
    rx_pin = 17
    # ADC
    # adc_pin = 26
    # led_pin = 'LED'

    # play_pin, v_dec_pin, v_inc_pin
    button_pins = {"play": 18, "v_dec": 19, "v_inc": 20}

    player = PlPlayer(DfpMini(tx_pin, rx_pin), button_pins)
    help(player)
    led = Led('LED')
    await player.reset()
    player.build_playlist(shuffled=False)
    print(f'Config: {player.config}')
    asyncio.create_task(led.show(2000))
    
    while True:
        await asyncio.sleep_ms(1000)


if __name__ == '__main__':
    try:
        asyncio.run(main())
    finally:
        asyncio.new_event_loop()  # clear retained state
        print('execution complete')
    