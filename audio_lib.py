# SPDX-FileCopyrightText: 2020 Jeff Epler for Adafruit Industries
#
# SPDX-License-Identifier: MIT

# audio_lib.py

"""
    CircuitPython Essentials Audio Out: plays MP3 and WAV files
    See: https://learn.adafruit.com/circuitpython-essentials/
                 circuitpython-audio-out
    Adapted by David Jones for Famous Trains, Derby. 2023
    
    Module of classes and functions for:
    - play_audio.py
    - play_audio_i2s.py
    
    - plays .mp3 and .wav files from a micro SD card
    - line-level or I2S output:
        -- passed as audio_out to play_audio()
    - supports mono or stereo, at 22 KHz sample rate
        (or less) and 16-bit WAV format (ref. above)
    - class inheritance is not used (V 7.3.3 bug)
    Tip:
    edit audio files to fade-in and fade-out to minimise clicks
"""

# hardware io
from digitalio import DigitalInOut, Direction, Pull

# audio
from audiomp3 import MP3Decoder
from audiocore import WaveFile
    
# SD storage
import busio
import sdcardio
import storage
import os

# other
from random import randint
import gc  # garbage collection for RAM


def shuffle(tuple_):
    """ return a shuffled copy of a tuple
        - Durstenfeld / Fisher-Yates shuffle algorithm """
    n = len(tuple_)
    if n < 2:
        return tuple_
    s_list = list(tuple_)
    limit = n - 1
    for i in range(limit):  # exclusive range
        j = randint(i, limit)  # inclusive range
        s_list[i], s_list[j] = s_list[j], s_list[i]
    return tuple(s_list)


def file_ext(name_):
    """ return file extension as lower-case string """
    if name_.rfind('.', 1) > 0:
        ext_ = name_.rsplit('.', 1)[1].lower()
    else:
        ext_ = ''
    return ext_


def get_audio_filenames(dir_, ext_list=('mp3', 'wav')):
    """ from folder, return a tuple of ext_list type files
        - CircuitPython libraries replay .mp3 or .wav files
        - skip system files with first char == '.' """
    return tuple([f for f in os.listdir(dir_)
                  if f[0] != '.' and file_ext(f) in ext_list])
    

class SdReader:
    """ sd card reader, SPI protocol
    	- mounted as 'sd/' by default """

    def __init__(self, clock, mosi, miso, cs, sd_dir='sd/'):
        self._dir = sd_dir
        spi = busio.SPI(clock, MOSI=mosi, MISO=miso)
        sd_card = sdcardio.SDCard(spi, cs)
        vfs = storage.VfsFat(sd_card)
        storage.mount(vfs, sd_dir)
        print(f'SD card reader mounted as: {self.dir}')
    
    @property
    def dir(self):
        """ returns mounted directory """
        return self._dir


class Button:
    """ input button, pull-up logic """

    def __init__(self, pin_):
        self._pin_in = DigitalInOut(pin_)
        self._pin_in.direction = Direction.INPUT
        self._pin_in.pull = Pull.UP

    @property
    def is_off(self):
        """ True if button is not pressed """
        return self._pin_in.value

    @property
    def is_on(self):
        """ True if button is pressed """
        return not self._pin_in.value


class PinOut:
    """ output pin """
    
    def __init__(self, pin_):
        self._pin_out = DigitalInOut(pin_)
        self._pin_out.direction = Direction.OUTPUT
        self.state = False
        
    @property
    def state(self):
        """ pin state """
        return self._pin_out.value
    
    @state.setter
    def state(self, value):
        self._pin_out.value = value
    

def play_audio(m_dir, files, audio_out,
               play_btns, skip_btn, wait_led=None):
    """ play mp3 and wav files under button control """

    off = False
    on = True

    if wait_led:
        wait_led.state = off
    mp3_decoder = None
    # instantiate MP3 decoder if required
    for filename in files:
        if file_ext(filename) == 'mp3':
            audio_file = open(m_dir + filename, 'rb')
            mp3_decoder = MP3Decoder(audio_file)
            break  # instantiate once only
    
    list_len = len(files)
    list_index = 0
    while True:
        filename = files[list_index]
        audio_file = open(m_dir + filename, 'rb')
        ext = file_ext(filename)
        if ext == 'mp3':
            mp3_decoder.file = audio_file
            audio_out.play(mp3_decoder)
        elif ext == 'wav':
            wave = WaveFile(audio_file)
            audio_out.play(wave)
        print(f'playing: {filename}')

        while audio_out.playing:
            if skip_btn.is_on:
                audio_out.stop()
        print('Waiting for button press ...')
        gc.collect()  # free up memory between plays
        wait_flag = True
        if wait_led:
            wait_led.state = on
        while wait_flag:
            for button in play_btns:
                if button.is_on:
                    wait_flag = False
        if wait_led:
            wait_led.state = off
        list_index += 1
        list_index %= list_len


def main():
    pass


if __name__ == '__main__':
    main()
