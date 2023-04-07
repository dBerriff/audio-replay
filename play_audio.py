# SPDX-FileCopyrightText: 2020 Jeff Epler for Adafruit Industries
#
# SPDX-License-Identifier: MIT

# play_audio.py

"""
    CircuitPython Essentials Audio Out: plays MP3 and WAV files
    See: https://learn.adafruit.com/circuitpython-essentials/
                 circuitpython-audio-out
    Adapted by David Jones for Famous Trains, Derby. 2023
    Hardware: David Herbert
    
    - line-level mono output
"""

import board  # CircuitPython

# AudioOut module is board-dependent
# this is for Rapberry Pi Pico
from audiopwmio import PWMAudioOut as AudioOut

# required classes and functions
from audio_lib import Button, PinOut, SdReader, AudioPlayer, shuffle

     
def main():
    """ play audio files under button control
        - pins for Cytron Maker Pi Pico board """
    
    # === USER parameters ===
    
    audio_folder = 'audio'

    # button pins
    play_pins = board.GP20, board.GP21
    skip_pin = board.GP22  # useful while testing

    # audio-out pin (mono)
    audio_pin = board.GP18  # Cytron jack socket

    # LED: indicates waiting for Play button push
    led_pin = board.LED
    
    # === end USER parameters ===
    
    if audio_folder[-1] != '/':
        audio_folder += '/'
    # assign the board pins
    # play_buttons: list or tuple
    if type(play_pins) != tuple:  # checking type(Pin) throws error
        play_buttons = Button(play_pins),
    else:
        play_buttons = tuple(Button(pin) for pin in play_pins)
    skip_btn = Button(skip_pin)
    led_out = PinOut(led_pin)
    
    # sd card reader is hard-wired; not user parameters
    # sd card for Cytron Maker Pi Pico
    sd_card = SdReader(board.GP10,  # clock
                       board.GP11,  # mosi
                       board.GP12,  # miso
                       board.GP15)  # cs
    # default sd_card.dir is: '/sd/'
    audio_folder = sd_card.dir + audio_folder
    print(f'audio folder is: {audio_folder}')

    # for line-level output
    audio_channel = AudioOut(audio_pin)

    audio_player = AudioPlayer(audio_folder, audio_channel,
                               play_buttons, skip_btn, led_out)
        
    # optional: shuffle the audio filenames sequence
    audio_player.files = shuffle(audio_player.files)
    print(f'audio files:\n{audio_player.files}')
    print()
    audio_player.play_audio_file(audio_player.files[0])
    audio_player.wait_audio_finish()
    audio_player.play_audio_files()


if __name__ == '__main__':
    main()
