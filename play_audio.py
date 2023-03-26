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
from audio_lib import Button, PinOut, SdReader, \
     get_audio_filenames, play_audio, shuffle
     

def main():
    """ test: play audio files under button control
        - pins for Cytron Maker Pi Pico """
    
    # === USER parameters ===
    
    audio_folder = 'audio/'

    # button pins
    play_pin_1 = board.GP20  # public
    play_pin_2 = board.GP21  # operator
    skip_pin = board.GP22  # useful for testing

    # audio-out pin (mono)
    audio_pin = board.GP18  # Cytron jack socket
    
    # LED: waiting for Play button push
    # onboard LED pin is: GP25 on standard Pico
    led_pin = PinOut(board.GP25)

    # === end USER parameters ===
    
    # set up the GP pins
    # buttons
    play_btns = (Button(play_pin_1), Button(play_pin_2))
    skip_btn = Button(skip_pin)
    # sd card
    clock = board.GP10
    mosi = board.GP11
    miso = board.GP12
    cs = board.GP15

    # instantiate card reader; default mount is '/sd'
    # default .dir is: '/sd/'
    sd_card = SdReader(clock, mosi, miso, cs)
    audio_folder = sd_card.dir + audio_folder
    print(f'audio folder is: {audio_folder}')

    music_filenames = get_audio_filenames(audio_folder)
    music_filenames = shuffle(music_filenames)  # optional
    
    # play music
    play_audio(audio_folder, music_filenames,
               AudioOut(audio_pin),
               play_btns, skip_btn, led_pin)


if __name__ == '__main__':
    main()
