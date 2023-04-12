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

    - play .mp3 and .wav files from a micro SD card or
      CircuitPython storage

    User and hardware settings are taken from settings.py

    Note: class inheritance is not used (CP V7.3.3 bug)
"""

# hardware
from digitalio import DigitalInOut, Direction, Pull

# audio
from audiomp3 import MP3Decoder
from audiocore import WaveFile
from audiopwmio import PWMAudioOut as AudioOut
from audiobusio import I2SOut


# SD storage
import busio
import sdcardio
import storage

# other
import os
import sys
from random import randint
import gc  # garbage collection for RAM
from time import sleep

# user and device settings
import settings


def file_ext(name_: str) -> str:
    """ return lower-case file extension """
    if name_.rfind('.', 1) > 0:
        ext_ = name_.rsplit('.', 1)[1].lower()
    else:
        ext_ = ''
    return ext_


def shuffle(tuple_: tuple) -> tuple:
    """ return a shuffled tuple of a tuple or list
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


class SdReader:
    """ sd card reader, SPI protocol """

    def __init__(self, clock, mosi, miso, cs, sd_dir='/sd'):
        spi = busio.SPI(clock, MOSI=mosi, MISO=miso)
        try:
            sd_card = sdcardio.SDCard(spi, cs)
        except OSError:
            print('SD card not found.')
            sys.exit()
        vfs = storage.VfsFat(sd_card)
        storage.mount(vfs, sd_dir)
        self.file_dir = sd_dir + '/'


class Button:
    """ input button, pull-up logic
        - inheritance gives incorrect return for: value """

    def __init__(self, pin):
        self._pin_in = DigitalInOut(pin)
        self._pin_in.switch_to_input(Pull.UP)

    @property
    def is_on(self) -> bool:
        """ pull-up logic for button pressed """
        return not self._pin_in.value

    @property
    def is_off(self) -> bool:
        """ pull-up logic for button not pressed """
        return self._pin_in.value


class PinOut:
    """ output pin """

    def __init__(self, pin):
        self._pin_out = DigitalInOut(pin)
        self._pin_out.switch_to_output()

    @property
    def state(self) -> bool:
        """ pin state """
        return self._pin_out.value

    @state.setter
    def state(self, value):
        self._pin_out.value = value


class AudioPlayer:
    """ play audio files under button control
        - only one instance is supported by CP running on a Pico
            -- CP reports insufficient number of timers
        - audio is an MP3 or WAV file
        - plays all audio files in: m_dir
        - audio_channel can be line or I2S output
        - CircuitPython supports mono and stereo audio,
            at 22 KHz sample rate (or less) and
            16-bit WAV format
        See: https://learn.adafruit.com/circuitpython-essentials/
             circuitpython-audio-out  
    """

    # for LED pin
    off = False
    on = True

    ext_set = {'mp3', 'wav'}

    def __init__(self, media_dir: str, audio_channel: AudioOut,
                 play_buttons: tuple, skip_button: Button,
                 wait_led: PinOut,
                 button_mode: bool):
        self.media_dir = media_dir
        self._audio_channel = audio_channel
        self._play_buttons = play_buttons
        self._skip_button = skip_button
        self._wait_led = wait_led
        self._button_mode = button_mode
        self.files = self.get_audio_filenames()
        self._decoder = self._set_decoder()

    def get_audio_filenames(self) -> tuple:
        """ from folder, return a list of type in ext_list
            - CircuitPython libraries replay .mp3 or .wav files
            - skip system files with first char == '.' """
        try:
            file_list = os.listdir(self.media_dir)
        except OSError:
            print(f'Error in reading directory: {self.media_dir}')
            sys.exit()
        # return audio filenames skipping system files starting with '.'
        return tuple((f for f in file_list
                      if f[0] != '.' and file_ext(f) in self.ext_set))

    def shuffle_files(self):
        """ shuffle the file list """
        self.files = shuffle(self.files)

    def wait_audio_finish(self):
        """ wait for audio to complete or skip_button pressed """
        while self._audio_channel.playing:
            if self._skip_button.is_on:
                self._audio_channel.stop()

    def wait_button_press(self):
        """ wait for a button to be pressed """
        print('Waiting for button press ...')
        wait = True
        while wait:
            for button in self._play_buttons:
                if button.is_on:
                    wait = False

    def _set_decoder(self) -> MP3Decoder:
        """ return decoder if .mp3 file found
            else set to None """
        decoder = None
        for filename in self.files:
            if file_ext(filename) == 'mp3':
                # decoder instantiation requires a file
                decoder = MP3Decoder(open(self.media_dir + filename, 'rb'))
                break  # instantiate once only
        return decoder

    def play_audio_file(self, filename: str, print_name: bool = True):
        """ play single audio file """
        try:
            audio_file = open(self.media_dir + filename, 'rb')
        except OSError:
            print(f'File not found: {filename}')
            return
        ext = file_ext(filename)
        if ext == 'mp3':
            self._decoder.file = audio_file
            stream = self._decoder
        elif ext == 'wav':
            stream = WaveFile(audio_file)
        else:
            print(f'Cannot play: {filename}')
            return
        if print_name:
            print(f'playing: {filename}')
        self._audio_channel.play(stream)

    def play_all_files(self):
        """ play mp3 and wav files under button control
            - start with file [1]; [0] used for startup test """
        n_files = len(self.files)
        list_index = 0
        while True:
            list_index += 1
            list_index %= n_files
            filename = self.files[list_index]
            gc.collect()  # free up memory between plays
            self._wait_led.state = self.on
            if self._button_mode:
                self.wait_button_press()  # play-button
            else:
                sleep(0.2)  # avoid multiple skip-button reads
            self._wait_led.state = self.off
            self.play_audio_file(filename, print_name=True)
            self.wait_audio_finish()


def main():
    """ play audio files on a Pi Pico
        - pins for Cytron Maker Pi Pico board """

    # assign the board pins
    # play_buttons: list or tuple

    if type(settings.play_pins) != tuple:  # checking type(Pin) throws error
        play_buttons = Button(settings.play_pins),
    else:
        play_buttons = tuple(Button(pin) for pin in settings.play_pins)
    skip_btn = Button(settings.skip_pin)
    led_out = PinOut(settings.led_pin)

    audio_folder = settings.folder

    # mount SD-card if required
    if audio_folder.find('/sd/') == 0:
        sd_card = SdReader(clock=settings.clock,
                           mosi=settings.mosi, miso=settings.miso,
                           cs=settings.cs,
                           sd_dir=settings.sd_dir)
        print(f'SD card mounted as: {sd_card.file_dir}')
    print(f'audio folder requested: {audio_folder}')

    # audio output
    if settings.i2s_out:
        o_stream = I2SOut(settings.bit_clock, settings.word_select, settings.data)
    else:
        o_stream = AudioOut(settings.audio_pin)
    audio_player = AudioPlayer(audio_folder, o_stream,
                               play_buttons, skip_btn, led_out,
                               button_mode=settings.button_control)
    # optional: shuffle the audio filenames sequence
    if settings.shuffle:
        audio_player.shuffle_files()
    print(f'audio files:\n{audio_player.files}')
    print()
    # play a file at startup to check system
    audio_player.play_audio_file(audio_player.files[0])
    audio_player.wait_audio_finish()
    audio_player.play_all_files()


if __name__ == '__main__':
    main()
