# SPDX-FileCopyrightText: 2020 Jeff Epler for Adafruit Industries
#
# SPDX-License-Identifier: MIT

# audio_lib.py

"""
    CircuitPython Essentials Audio Out: plays MP3 and WAV files
    See: https://learn.adafruit.com/circuitpython-essentials/
                 circuitpython-audio-out
    Adapted by David Jones for Famous Trains, Derby. 2023

    - play .mp3 and .wav files from a micro SD card

    As module: classes and functions for:
    - play_audio.py (included in this file as main())
    - play_audio_i2s.py

    Note: class inheritance is not used (V 7.3.3 bug)
"""

# hardware
from digitalio import DigitalInOut, Direction, Pull

# audio
from audiomp3 import MP3Decoder
from audiocore import WaveFile
    
# SD storage
import busio
import sdcardio
import storage
import os
import sys

# other
from random import randint
import gc  # garbage collection for RAM


def shuffle(tuple_) -> tuple:
    """ return a shuffled tuple of a tuple (or list)
        - Durstenfeld / Fisher-Yates shuffle algorithm """
    n = len(tuple_)
    if n < 2:
        return tuple_
    s_list = list(tuple_)
    limit = n - 1
    for i in range(limit):  # exclusive range
        j = randint(i, limit)  # inclusive range
        if j != i:
            s_list[i], s_list[j] = s_list[j], s_list[i]
    return tuple(s_list)


def file_ext(name_) -> str:
    """ return lower-case file extension """
    if name_.rfind('.', 1) > 0:
        ext_ = name_.rsplit('.', 1)[1].lower()
    else:
        ext_ = ''
    return ext_


class SdReader:
    """ sd card reader, SPI protocol """

    def __init__(self, clock, mosi, miso, cs, sd_dir='/sd'):
        self.dir = sd_dir + '/'
        spi = busio.SPI(clock, MOSI=mosi, MISO=miso)
        try:
            sd_card = sdcardio.SDCard(spi, cs)
        except OSError:
            print('No SD card')
            sys.exit()
        vfs = storage.VfsFat(sd_card)
        storage.mount(vfs, sd_dir)


class Button:
    """ input button, pull-up logic """

    def __init__(self, pin):
        self._pin_in = DigitalInOut(pin)
        self._pin_in.direction = Direction.INPUT
        self._pin_in.pull = Pull.UP

    @property
    def is_off(self) -> bool:
        """ pull-up logic for button not pressed """
        return self._pin_in.value

    @property
    def is_on(self) -> bool:
        """ pull-up logic for button pressed """
        return not self._pin_in.value


class PinOut:
    """ output pin """
    
    def __init__(self, pin):
        self._pin_out = DigitalInOut(pin)
        self._pin_out.direction = Direction.OUTPUT
        self.state = False
        
    @property
    def state(self) -> bool:
        """ pin state """
        return self._pin_out.value
    
    @state.setter
    def state(self, value):
        self._pin_out.value = value


class AudioPlayer:
    """ play audio files under button control
        - audio is MP3 or WAV files
        - plays all audio files in m_dir
        - audio_channel can be a line or I2S output
        - CircuitPython supports mono and stereo audio,
            at 22 KHz sample rate (or less) and
            16-bit WAV format
        See: https://learn.adafruit.com/circuitpython-essentials/
             circuitpython-audio-out
        
        """
    # for buttons
    off = False
    on = True

    def __init__(self, m_dir, audio_channel,
                 play_buttons, skip_button, wait_led):
        self.m_dir = m_dir
        self.audio_channel = audio_channel
        self.play_buttons = play_buttons
        self.skip_button = skip_button
        self.wait_led = wait_led
        self.ext_list = ('mp3', 'wav')
        self.files = self.get_audio_filenames()
        self.decoder = self._set_decoder()

    def get_audio_filenames(self) -> tuple:
        """ from folder, return a list of type in ext_list
            - CircuitPython libraries replay .mp3 or .wav files
            - skip system files with first char == '.' """
        try:
            file_list = os.listdir(self.m_dir)
        except OSError:
            print(f'Error in reading directory: {self.m_dir}') 
            sys.exit()
        return tuple([f for f in file_list
                      if f[0] != '.' and file_ext(f) in self.ext_list])

    def wait_audio_finish(self):
        """ wait for audio to complete or skip_button pressed """
        while self.audio_channel.playing:
            if self.skip_button.is_on:
                self.audio_channel.stop()

    def wait_button_press(self):
        """ wait for a button to be pressed """
        print('Waiting for button press ...')
        wait = True
        while wait:
            for button in self.play_buttons:
                if button.is_on:
                    wait = False

    def _set_decoder(self):
        """ return decoder if required else None """
        decoder = None
        for filename in self.files:
            if file_ext(filename) == 'mp3':
                # decoder instantiation requires a file
                audio_file = open(self.m_dir + filename, 'rb')
                decoder = MP3Decoder(audio_file)
                break  # instantiate once only
        return decoder

    def play_audio_file(self, filename):
        """ play single audio file, wav or mp3 """
        try:
            audio_file = open(self.m_dir + filename, 'rb')
        except OSError:
            print(f'file not found: {filename}')
            return
        ext = file_ext(filename)
        if ext == 'mp3':
            self.decoder.file = audio_file
            self.audio_channel.play(self.decoder)
        elif ext == 'wav':
            wave = WaveFile(audio_file)
            self.audio_channel.play(wave)

    def play_audio_files(self):
        """ play mp3 and wav files under button control """
        list_index = 0
        while True:
            self.wait_led.state = self.off
            filename = self.files[list_index]
            # optional print statement
            print(f'playing: {filename}')
            self.play_audio_file(filename)
            self.wait_audio_finish()
            gc.collect()  # free up memory between plays
            self.wait_led.state = self.on
            self.wait_button_press()
            # set index for next file
            list_index = (list_index + 1) % len(self.files)


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
    print(f'audio files: {audio_player.files}')
    print()
    audio_player.play_audio_files()


if __name__ == '__main__':
    main()
