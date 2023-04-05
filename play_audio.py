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

import board  # CircuitPython

# AudioOut module is board-dependent
try:
    from audioio import AudioOut
except ImportError:
    from audiopwmio import PWMAudioOut as AudioOut

# required classes and functions
from audio_lib import Button, PinOut, SdReader, AudioPlayer, shuffle

     
def main():
    """ test: play audio files under button control
        - pins for Cytron Maker Pi Pico board """
    
    # === USER parameters ===
    
    audio_folder = 'audio/'

    # button pins
    play_pins = board.GP20, board.GP21  # public
    skip_pin = board.GP22  # useful while testing

    # audio-out pin (mono)
    audio_pin = board.GP19  # Cytron jack socket

    # LED: indicates waiting for Play button push
    # onboard LED pin is: standard Pico: GP25
    led_pin = board.GP25
    
    # === end USER parameters ===
    
    # assign the board pins
    if type(play_pins) != tuple:  # checking for type Pin gave error
        play_pins = play_pins,
    # buttons
    play_buttons = tuple(Button(pin) for pin in play_pins)
    skip_btn = Button(skip_pin)
    led_out = PinOut(led_pin)
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
                               play_buttons, skip_btn, led_out)
        
    # optional: shuffle the file order
    audio_player.files = shuffle(audio_player.files)
    print(f'audio files: {audio_player.files}')
    print()
    audio_player.play_audio_files()


if __name__ == '__main__':
    main()
