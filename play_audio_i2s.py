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
    """ play audio files under button control """

    # === USER parameters ===
    
    audio_folder = 'audio/'
    # audio_folder = ''  # uncomment if no folder

    # button pins
    play_pin_1 = board.GP20
    play_pin_2 = board.GP21
    skip_pin = board.GP22

    # I2S out pins
    # - word_select_pin must be bit_clock_pin + 1 
    bit_clock_ = board.GP16
    word_select_ = board.GP17
    data_ = board.GP18


    # LED: waiting for Play button push
    led_pin = PinOut(board.GP0)  # = None if not used
    # led_pin = None  # uncomment if not used

    # === end USER parameters ===

    play_btns = (Button(play_pin_1), Button(play_pin_2))
    skip_btn = Button(skip_pin)

    # sd card pins for Cytron Maker Pi Pico card reader
    clock = board.GP10
    mosi = board.GP11
    miso = board.GP12
    cs = board.GP15

    # instantiate card reader; mount as "/sd"
    sd_card = SdReader(clock, mosi, miso, cs, '/sd')
    
    music_files = get_audio_filenames(sd_card.dir + audio_folder)
    music_files = shuffle(music_files)
    
    # instantiate I2S out
    audio_outout = I2SOut(bit_clock_, word_select_, data_)
    # play audio
    play_audio(sd_card.dir, music_files,
               audio_outout, play_btns, skip_btn, led_pin)


if __name__ == '__main__':
    main()
