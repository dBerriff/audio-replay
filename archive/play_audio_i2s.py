# SPDX-FileCopyrightText: 2020 Jeff Epler for Adafruit Industries
#
# SPDX-License-Identifier: MIT

# play_audio.py
"""
    CircuitPython (CP) Essentials Audio Out: plays MP3 and WAV files
    See: https://learn.adafruit.com/circuitpython-essentials/
                 circuitpython-audio-out
    Adapted for Famous Trains, Derby 2023
    Software: David Jones
    Hardware: David Herbert

    - play .mp3 and .wav files from a micro SD card or
      CP storage

    - User and hardware settings are taken from settings.py
    
    - Simple multiple button reads to reject single noise spikes 

    Note: class inheritance is not used (CP V7.3.3 bug)
"""
# import:
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

# device settings
from archive import settings


def file_ext(name_: str) -> str:
    """ return lower-case file extension """
    if name_.rfind('.', 1) > 0:
        ext_ = name_.rsplit('.', 1)[1].lower()
    else:
        ext_ = ''
    return ext_


def shuffle(tuple_: tuple) -> tuple:
    """ return a shuffled tuple (or list)
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
        - sd_dir name must be, or start with, '/sd' """

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
    
    # debounce values
    n_checks = 3
    i_max = n_checks - 1  # max list track_index
    check_pause = 0.02  # around 20ms for typical de-bounce

    def __init__(self, pin):
        self.pin = pin
        self._pin_in = DigitalInOut(pin)
        self._pin_in.switch_to_input(Pull.UP)
        # for de-bounce readings (workspace)
        self._inputs = [1] * self.n_checks
    
    def __str__(self):
        """ print() string for Button """
        return f'Button pin: {self.pin}; Input: {self._inputs}'

    def get_state(self) -> bool:
        """ de-bounced check for button pressed
            - button-press sets return to 1
            - reverses pull-up logic
        """
        pin_ = self._pin_in
        input_list = self._inputs
        for i in range(self.i_max):
            input_list[i] = pin_.value
            sleep(self.check_pause)
        input_list[self.i_max] = pin_.value
        return 1 if not any(input_list) else 0  # all readings 0 for On


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

    ext_set = {'mp3', 'wav'}

    def __init__(self, media_dir: str, audio_channel: AudioOut):
        self.media_dir = media_dir
        self._audio_channel = audio_channel
        self.play_buttons = None
        self.skip_button = None
        self.button_mode = False
        self.print_f_name = False
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
        """ wait for:
            - play to complete or
            - skip_button pressed if exists """
        s_button = self.skip_button
        while self._audio_channel.playing:
            if s_button and s_button.get_state() == 1:
                self._audio_channel.ch_pause()
                print(s_button)

    def wait_button_press(self):
        """ wait for a button to be pressed
            - pause between checks """
        print('Waiting for button press ...')
        while True:
            # blocks until a play button is pressed
            for button in self.play_buttons:                    
                if button.get_state() == 1:
                    print(button)
                    return
            sleep(Button.check_pause)

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
        if self.print_f_name:
            print(f'playing: {filename}')
        self._audio_channel.ch_play(stream)

    def play_all_files(self):
        """ play mp3 and wav files under button control
            - start with file [1]; [0] used for startup test """
        n_files = len(self.files)
        list_index = -1
        while True:
            list_index = (list_index + 1) % n_files
            filename = self.files[list_index]
            gc.collect()  # free up memory between plays
            if self.button_mode:
                self.wait_button_press()  # play-button
            else:
                sleep(0.2)  # avoid multiple skip-button reads
            self.play_audio_file(filename)
            self.wait_audio_finish()


def main():
    """ play audio files on a Pi Pico
        - pins for Cytron Maker Pi Pico board """
    # turn Pico LED on to confirm power-on and main.py running
    led = DigitalInOut(settings.LED)
    led.direction = Direction.OUTPUT
    led.value = True
    # the settings values are assigned within the settings module
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

    audio_player = AudioPlayer(audio_folder, o_stream)
    if play_buttons:
        audio_player.play_buttons = play_buttons
        audio_player.button_mode = True
    else:
        audio_player.button_mode = False
    if skip_button:
        audio_player.skip_button = skip_button

    # optional: shuffle the audio filenames sequence
    if settings.shuffle:
        audio_player.shuffle_files()
    print(f'audio files:\n{audio_player.files}')
    print()
    audio_player.print_f_name = True
    
    # play a file at startup to check system
    audio_player.play_audio_file(audio_player.files[0])
    audio_player.wait_audio_finish()
    # turn Pico LED off
    led.value = False
    
    # play all files in a repeating loop
    # with button control if settings.button_control is True
    audio_player.play_all_files()


if __name__ == '__main__':
    main()
