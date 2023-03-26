# SPDX-FileCopyrightText: 2020 Jeff Epler for Adafruit Industries
#
# SPDX-License-Identifier: MIT

# play_audio_i2s.py

"""
    CircuitPython Essentials Audio Out: plays MP3 and WAV files
    See: https://learn.adafruit.com/circuitpython-essentials/
                 circuitpython-audio-out
    Adapted by David Jones for Famous Trains, Derby. 2023

    - I2S digital output

    I2SOut pins: bit_clock and word_select pins must be consecutive

      I2SOut pins  __>  MAX98357A (left to right)

          bit_clock   ___  __>  LRC
                         \/
          word_select ___/\__>  BCLK

          data        _______>  DIN
"""

import board

# audio
from audiobusio import I2SOut

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

    # LED: waiting for Play button push
    # onboard LED pin is: GP25 on standard Pico
    led_pin = PinOut(board.GP25)

    # I2S out pins
    # - word_select_pin must be bit_clock_pin + 1
    bit_clock_ = board.GP16
    word_select_ = board.GP17
    data_ = board.GP18

    # === end USER parameters ===

    # set up the GP pins
    # buttons
    play_buttons = (Button(play_pin_1), Button(play_pin_2))
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
               I2SOut(bit_clock_, word_select_, data_),
               play_buttons, skip_btn, led_pin)


if __name__ == '__main__':
    main()
