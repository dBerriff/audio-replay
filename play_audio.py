# SPDX-FileCopyrightText: 2020 Jeff Epler for Adafruit Industries
#
# SPDX-License-Identifier: MIT

# play_audio.py
"""
    CircuitPython (CP) Essentials Audio Out: plays MP3 and WAV files
    See: https://learn.adafruit.com/circuitpython-essentials/
                 circuitpython-audio-out
    Adapted by David Jones for Famous Trains, Derby. 2023
    Hardware: David Herbert

    - play .mp3 and .wav files from a micro SD card or
      CP storage

    - User and hardware settings are taken from settings.py
    
    - Simple multiple button reads to reject single noise spikes 

    Note: class inheritance is not used (CP V7.3.3 bug)
"""

# hardware
from digitalio import DigitalInOut, Direction, Pull
from board import LED

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

# device settings
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
    """ sd card reader, SPI protocol
        - sd_dir name must be or start with '/sd' """

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
    """ input button
        - Pull.UP logic
        - inheritance not used: CP bug """
    
    # class debounce values
    checks = 3  # should be sufficient? Minimum 1
    check_pause = 0.01  # approx. 0.02 / (checks - 1)

    # pull-up logic
    if checks > 1:
        inputs = []
        for _ in range(checks):
            inputs.append(True)
        check_limit = checks - 1  # no pause after final reading
    else:
        inputs = [True]
        check_limit = 0
        check_pause = 0.0

    def __init__(self, pin):
        self.pin = pin  # for diagnostics
        self._pin_in = DigitalInOut(pin)
        self._pin_in.switch_to_input(Pull.UP)
        self.inputs = list(Button.inputs)  # for diagnostics
    
    def __str__(self):
        """ print() string for Button """
        return f'Button pin: {self.pin}; Input: {self.inputs}'

    @property
    def is_on(self) -> bool:
        """ pull-up logic for button pressed
            - button-press sets input False """
        # take n_readings - suggest over approx. 20ms
        index = 0
        while index < self.check_limit:
            # all except final input
            self.inputs[index] = self._pin_in.value
            index += 1
            sleep(self.check_pause)
        self.inputs[index] = self._pin_in.value
        return not any(self.inputs)  # pull-up readings must be False for On


class PinOut:
    """ output pin """

    def __init__(self, pin):
        self._pin_out = DigitalInOut(pin)
        self._pin_out.switch_to_output()

    @property
    def state(self):
        """ pin state """
        return self._pin_out.value

    @state.setter
    def state(self, value: bool):
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
                 button_mode: bool, print_f_name: bool):
        self.media_dir = media_dir
        self._audio_channel = audio_channel
        self._play_buttons = play_buttons
        self._skip_button = skip_button
        self._wait_led = wait_led
        self._button_mode = button_mode
        self.print_name = print_f_name
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
        """ wait for play to complete or skip_button pressed """
        while self._audio_channel.playing:
            if self._skip_button and self._skip_button.is_on:
                print(self._skip_button)
                self._audio_channel.stop()

    def wait_button_press(self, diagnose=False):
        """ wait for a button to be pressed """
        print('Waiting for button press ...')
        while True:
            # blocks until a play button is pressed
            for button in self._play_buttons:
                if button.is_on:
                    print(button)
                    return
                if diagnose:
                    print(button)

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

    def play_audio_file(self, filename: str):
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
        if self.print_name:
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
                self.wait_button_press(diagnose=settings.diagnose)  # play-button
            else:
                sleep(0.2)  # avoid multiple skip-button reads
            self._wait_led.state = self.off
            self.play_audio_file(filename)
            self.wait_audio_finish()


def main():
    """ play audio files on a Pi Pico
        - pins for Cytron Maker Pi Pico board """

    # assign the board pins
    if settings.play_pins:  # not None
        if type(settings.play_pins) != tuple:
            # convert single value to tuple
            play_buttons = Button(settings.play_pins),
        else:
            play_buttons = tuple(Button(pin) for pin in settings.play_pins)
    else:
        play_buttons = None
    if settings.skip_pin:  # not None
        skip_button = Button(settings.skip_pin)
    else:
        skip_button = None
    print('Buttons:')
    for button in play_buttons:
        print(button)
    print(skip_button)
    if settings.led_pin:  # not None
        led_out = PinOut(settings.led_pin)
    else:
        led_out = PinOut(LED)

    audio_folder = settings.folder

    # mount SD-card if required
    if audio_folder.find('/sd') == 0:
        sd_card = SdReader(clock=settings.clock,
                           mosi=settings.mosi, miso=settings.miso,
                           cs=settings.cs,
                           sd_dir=settings.sd_dir)
        print(f'SD card mounted as: {sd_card.file_dir}')
    print(f'audio folder requested: {audio_folder}')
    print()

    # audio output
    if settings.i2s_out:
        o_stream = I2SOut(settings.bit_clock, settings.word_select, settings.data)
    else:
        o_stream = AudioOut(settings.audio_pin)
    audio_player = AudioPlayer(audio_folder, o_stream,
                               play_buttons, skip_button, led_out,
                               button_mode=settings.button_control,
                               print_f_name=True)
    
    # optional: shuffle the audio filenames sequence
    if settings.shuffle:
        audio_player.shuffle_files()
    print(f'audio files:\n{audio_player.files}')
    print()
    
    # play a file at startup to check system
    audio_player.play_audio_file(audio_player.files[0])
    audio_player.wait_audio_finish()
    
    # play all files in a repeating loop
    # with button control if settings.button_control is True
    audio_player.play_all_files()


if __name__ == '__main__':
    main()
