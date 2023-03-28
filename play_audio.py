# SPDX-FileCopyrightText: 2020 Jeff Epler for Adafruit Industries
#
# SPDX-License-Identifier: MIT

# play_audio.py

"""
    CircuitPython Essentials Audio Out: plays MP3 and WAV files
    See: https://learn.adafruit.com/circuitpython-essentials/
                 circuitpython-audio-out
    Adapted by David Jones for Famous Trains, Derby. 2023
    
    - line-level mono output
"""

import board

# audio - line-level on a single GP pin
# module is board-dependent
try:
    from audioio import AudioOut
except ImportError:
    from audiopwmio import PWMAudioOut as AudioOut

# required classes and functions
from audio_lib import Button, PinOut, SdReader, AudioPlayer
     

def main():
    """ test: play audio files under button control
        - pins for Cytron Maker Pi Pico board """
    
    import board

    # AudioOut - line-level audio on a single GP pin
    # module is board-dependent:
    try:
        from audioio import AudioOut
    except ImportError:
        from audiopwmio import PWMAudioOut as AudioOut

    # === USER parameters ===
    
    audio_folder = 'audio/'

    # button pins
    play_pin_1 = board.GP20  # public
    play_pin_2 = board.GP21  # operator
    skip_pin = board.GP22  # useful while testing

    # audio-out pin (mono)
    audio_pin = board.GP18  # Cytron jack socket

    # LED: indicates waiting for Play button push
    # onboard LED pin is: standard Pico: GP25
    led_pin = PinOut(board.GP25)
    
    # === end USER parameters ===
    
    # assign the board pins
    # buttons
    play_buttons = (Button(play_pin_1), Button(play_pin_2))
    skip_btn = Button(skip_pin)
    # sd card for Cytron Maker Pi Pico
    # root sd_card.dir is: '/sd/'
    sd_card = SdReader(board.GP10,  # clock
                       board.GP11,  # mosi
                       board.GP12,  # miso
                       board.GP15)  # cs
    audio_folder = sd_card.dir + audio_folder
    print(f'audio folder is: {audio_folder}')

    # for line-level output
    audio_channel = AudioOut(audio_pin)

    audio_player = AudioPlayer(audio_folder, audio_channel,
                               play_buttons, skip_btn, led_pin)
    audio_player.play_audio_list()


if __name__ == '__main__':
    main()
